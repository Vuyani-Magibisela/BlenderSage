# SPDX-License-Identifier: GPL-3.0-or-later
"""Merge a recording's action and state journals into draft steps and review items.

Follows the merge rules in docs/plan.md ("Recorder design"):
1. Each supported OPERATOR/PROPERTY report is one action; repeated edits of the same
   property with nothing in between collapse to the final value.
2. A state change no action explains becomes a draft from the state diff.
3. Undo and redo are matched against the state journal; work undone and not redone is
   left out, and an unclear match becomes a review item.
4. Unsupported or unreadable reports become review items, never silent drops.
5. Cancelled tools leave no report, so they are absent.

Report messages are evidence only: they are parsed with ast and literal_eval and
never executed. generate() returns a DraftResult with `items` (drafts and review items
in recording order) and `ignored` (everything left out, with the reason).
"""
import ast
import bisect
import math
import re
from dataclasses import dataclass, field

from .journal import read_journal
from .state_diff import apply_diff, diff_states

DRAFT, REVIEW = "draft", "review"

# Timing, from the recorder: reports are polled every 0.1 s; a diff is written at
# most once per throttle second (plus a 0.25 s tick), and while a tool is running a
# diff can be taken ~0.1 s before the tool's report (docs/m1-findings.md, Step 3).
EXPLAIN_BEFORE = 1.5    # a report up to this long before a diff can explain it
EXPLAIN_AFTER = 0.5     # ...or this long after it
MODAL_LOOKAHEAD = 10.0  # diffs taken during an interactive tool belong to its report
UNDO_WINDOW = 2.5       # how long after an undo/redo its diff can appear

SELECTION = frozenset({"active", "selected"})
EXISTENCE = frozenset({"exists"}) | SELECTION
ANY = None  # an action whose effect on the snapshot is unknown

# Reports about the interface itself (sidebar tabs, file browser folders, ...). Not
# steps; the file browser ones also carry the teacher's local folder paths.
UI_PREFIXES = (
    "bpy.context.region.",
    "bpy.context.area.",
    "bpy.context.screen.",
    "bpy.context.window.",
    "bpy.context.space_data.params.",
    "bpy.context.space_data.context",
)

# operator id -> (title, snapshot fields it changes)
OPERATORS = {
    "transform.translate": ("Move", {"location"}),
    "transform.rotate": ("Rotate", {"rotation"}),
    "transform.resize": ("Scale", {"scale", "dimensions"}),
    "transform.shrink_fatten": ("Shrink/Fatten", {"dimensions"}),
    "object.editmode_toggle": ("Toggle Edit Mode", {"mode"}),
    "object.mode_set": ("Switch mode", {"mode"}),
    "object.select_all": ("Select all", SELECTION),
    "object.delete": ("Delete", EXISTENCE),
    "object.duplicate_move": ("Duplicate", EXISTENCE | {"location"}),
    "object.duplicate_move_linked": ("Duplicate linked", EXISTENCE | {"location"}),
    "object.transform_apply": ("Apply transforms", {"location", "rotation", "scale", "dimensions"}),
    "object.modifier_add": ("Add modifier", {"modifiers", "dimensions"}),
    "object.modifier_remove": ("Remove modifier", {"modifiers", "dimensions"}),
    "object.modifier_apply": ("Apply modifier", {"modifiers", "dimensions"}),
    "object.subdivision_set": ("Add Subdivision Surface", {"modifiers", "dimensions"}),
    "object.shade_smooth": ("Shade Smooth", set()),
    "object.shade_flat": ("Shade Flat", set()),
    "object.shade_auto_smooth": ("Shade Auto Smooth", {"modifiers"}),
    "object.material_slot_add": ("Add material slot", {"materials"}),
    "object.material_slot_remove": ("Remove material slot", {"materials"}),
    "material.new": ("New material", {"materials"}),
    "mesh.select_mode": ("Change select mode", set()),
    "mesh.select_all": ("Select all", set()),
    "mesh.extrude_region_move": ("Extrude", {"dimensions"}),
    "mesh.extrude_region_shrink_fatten": ("Extrude along normals", {"dimensions"}),
    "mesh.inset": ("Inset faces", {"dimensions"}),
    "mesh.bevel": ("Bevel", {"dimensions"}),
    "mesh.loopcut_slide": ("Loop cut", {"dimensions"}),
    "mesh.subdivide": ("Subdivide", {"dimensions"}),
    "mesh.delete": ("Delete", {"dimensions"}),
}

# property path (after the object) -> snapshot fields it changes
PROPERTY_FIELDS = (
    (r"modifiers\[", {"modifiers", "dimensions"}),
    (r"(active_material|material_slots)\b", {"materials"}),
    (r"location(\[\d\])?$", {"location"}),
    (r"rotation_euler(\[\d\])?$", {"rotation"}),
    (r"scale(\[\d\])?$", {"scale", "dimensions"}),
    (r"dimensions(\[\d\])?$", {"dimensions", "scale"}),
    (r"name$", EXISTENCE),
)
_OBJECT_PATH = re.compile(
    r"bpy\.(?:context\.(?:object|active_object)|data\.objects\[(['\"])(?P<name>.+?)\1\])\.(?P<rest>.+)$")
_MATERIAL_PATH = re.compile(r"bpy\.data\.materials\[(['\"])(?P<name>.+?)\1\]\.(?P<rest>.+)$")


class ReportParseError(ValueError):
    pass


@dataclass
class Item:
    status: str           # DRAFT or REVIEW
    kind: str             # "action" (from a report), "state" (from a diff) or "event"
    title: str
    segment: int          # Blender session within the recording (time restarts after recovery)
    t: float
    reason: str = ""      # why a review item needs the teacher
    op: str = ""          # operator id or property path
    args: dict = field(default_factory=dict)
    objects: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    changes: dict = field(default_factory=dict)    # (object, field) -> value after
    check_hints: list = field(default_factory=list)
    affects: object = field(default=frozenset(), repr=False)   # fields it changes, or ANY
    before: dict = field(default_factory=dict, repr=False)     # state drafts: values before
    dropped: bool = field(default=False, repr=False)
    undo_match: bool = field(default=False, repr=False)


@dataclass
class Ignored:
    segment: int
    t: float
    reason: str
    text: str


@dataclass
class DraftResult:
    items: list
    ignored: list
    stats: dict

    @property
    def drafts(self):
        return [i for i in self.items if i.status == DRAFT]

    @property
    def review(self):
        return [i for i in self.items if i.status == REVIEW]


# Parsing (never executes anything) -----------------------------------------------------

def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        return ".".join([node.id] + parts[::-1])
    return None


def _literal(node):
    try:
        return ast.literal_eval(node)
    except ValueError:
        text = ast.unparse(node)
        if text.startswith("bpy."):  # a reference such as bpy.data.objects['Sphere']
            return {"ref": text}
        raise


def parse_report(rtype, message):
    """Return ("operator", op_id, kwargs) or ("property", path, {"value": v})."""
    try:
        if rtype == "OPERATOR":
            node = ast.parse(message, mode="eval").body
            name = _dotted(node.func) if isinstance(node, ast.Call) else None
            if not name or not name.startswith("bpy.ops.") or node.args:
                raise ReportParseError("not a bpy.ops call with keyword arguments")
            if any(kw.arg is None for kw in node.keywords):
                raise ReportParseError("** arguments")
            return "operator", name[len("bpy.ops."):], {kw.arg: _literal(kw.value) for kw in node.keywords}
        if rtype == "PROPERTY":
            body = ast.parse(message, mode="exec").body
            if len(body) != 1 or not isinstance(body[0], ast.Assign) or len(body[0].targets) != 1:
                raise ReportParseError("not a single assignment")
            path = ast.unparse(body[0].targets[0])
            if not path.startswith("bpy."):
                raise ReportParseError("not a bpy property")
            return "property", path, {"value": _literal(body[0].value)}
    except (SyntaxError, ValueError, TypeError, RecursionError) as exc:
        raise ReportParseError(str(exc)) from None
    raise ReportParseError(f"report type {rtype}")


# Formatting ----------------------------------------------------------------------------

def _num(v):
    if isinstance(v, float):
        return f"{round(v, 4):g}"
    if isinstance(v, (list, tuple)):
        return "(" + ", ".join(_num(x) for x in v) + ")"
    return repr(v) if isinstance(v, str) else str(v)


def _words(name):
    return name.replace("_euler", "").replace("_", " ").capitalize()


def _round(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, (list, tuple)):
        return [_round(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted(_round(x) for x in v)
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    return v


def _property_label(rest):
    m = re.match(r"modifiers\[(['\"])(.+?)\1\]\.(\w+)$", rest)
    if m:
        return f"{m.group(2)} modifier {_words(m.group(3)).lower()}"
    m = re.match(r"(\w+)\[([0-2])\]$", rest)
    if m:
        return f"{_words(m.group(1))} {'XYZ'[int(m.group(2))]}"
    return _words(rest.split(".")[-1])


def _operator_title(op, args, title):
    if op == "object.modifier_add" and "type" in args:
        return f"Add {_words(str(args['type']).lower()).title()} modifier"
    if op == "object.subdivision_set" and "level" in args:
        return f"Add Subdivision Surface (level {args['level']})"
    if op == "object.mode_set" and "mode" in args:
        return f"Switch to {_words(str(args['mode']).lower()).title()} Mode"
    if op == "mesh.select_mode" and "type" in args:
        return f"Switch to {str(args['type']).capitalize()} select mode"
    if op == "transform.translate" and "value" in args:
        return f"Move by {_num(args['value'])}"
    if op == "transform.resize" and "value" in args:
        v = args["value"]
        return f"Scale by {_num(v[0]) if len(set(v)) == 1 else _num(v)}"
    if op == "transform.rotate" and "value" in args:
        return f"Rotate {round(math.degrees(args['value']), 2):g}° around {args.get('orient_axis', '?')}"
    if op == "mesh.bevel" and "offset" in args:
        return f"Bevel (width {_num(args['offset'])}" + (f", {args['segments']} segments)" if "segments" in args else ")")
    if op == "mesh.inset" and "thickness" in args:
        return f"Inset faces (thickness {_num(args['thickness'])})"
    if op.startswith("mesh.extrude"):
        move = args.get("TRANSFORM_OT_translate", {}).get("value")
        if move is not None:
            return f"Extrude by {_num(move)}"
    return title


# Snapshot fields ----------------------------------------------------------------------

def _fields(changes):
    """Set of (object, field) a diff touches; added/removed objects become 'exists'."""
    out = {("", key) for key in ("mode", "active", "selected") if key in changes}
    objects = changes.get("objects", {})
    out |= {(row["name"], "exists") for row in objects.get("added", [])}
    out |= {(name, "exists") for name in objects.get("removed", [])}
    for name, row in objects.get("changed", {}).items():
        out |= {(name, f) for f in row}
    return out


def _value(state, key):
    obj, name = key
    if not obj:
        return state.get(name)
    row = next((o for o in state["objects"] if o["name"] == obj), None)
    if name == "exists":
        return row
    return None if row is None else row.get(name)


def _check_hints(changes):
    hints = []
    for (obj, name), v in sorted(changes.items(), key=lambda kv: kv[0]):
        if name == "mode":
            hints.append({"type": "mode", "value": v})
        elif name == "exists" and v is not None:
            hints.append({"type": "object_exists", "object": obj, "object_type": v["type"]})
        elif name in ("dimensions", "scale"):
            hints.append({"type": name, "object": obj, "value": _round(v)})
        elif name == "modifiers":
            hints += [{"type": "modifier", "object": obj, "modifier": m["type"], "settings": _round(m["settings"])}
                      for m in v]
        elif name == "materials" and v:
            hints.append({"type": "material_assigned", "object": obj, "name": v[0]})
    return hints


def _state_title(changes):
    objs = sorted({o for o, _ in changes if o})
    names = {n for _, n in changes}
    added = [o for (o, n), v in changes.items() if n == "exists" and v is not None]
    removed = [o for (o, n), v in changes.items() if n == "exists" and v is None]
    if added:
        return "Add " + ", ".join(sorted(added))
    if removed:
        return "Delete " + ", ".join(sorted(removed))
    if "dimensions" in names and names <= {"dimensions", "scale"} and len(objs) == 1:
        return f"Set {objs[0]} dimensions to {_num(changes[(objs[0], 'dimensions')])}"
    if names == {"mode"}:
        return f"Switch to {changes[('', 'mode')]} mode"
    fields = ", ".join(sorted(names - SELECTION) or sorted(names))
    return f"Change {', '.join(objs) or 'scene'}: {fields}"


# Generation ---------------------------------------------------------------------------

def _segment(entries, starts):
    """Pair entries with their segment: a new one starts at each start/recovered entry."""
    seg, out = -1, []
    for e in entries:
        if seg < 0 or _is_start(e, starts):
            seg += 1
        out.append((seg, e))
    return out


def _is_start(e, starts):
    return e.get("kind") in starts or (e.get("kind") == "snapshot" and e.get("reason") in starts)


class _States:
    """State after each state-journal entry, per segment, for lookups by time."""

    def __init__(self, entries):
        self.points = {}   # segment -> ([t], [state])
        self.diffs = []
        current = None
        for seg, e in _segment(entries, ("start", "recovered")):
            if e.get("kind") == "snapshot":
                before, current = current, e["full"]
                if e.get("reason") == "resume":
                    self.diffs.append({"seg": seg, "t": e["t"], "resume": True, "before": before, "after": current})
            elif e.get("kind") == "diff" and current is not None:
                before, current = current, apply_diff(current, e["changes"])
                self.diffs.append({"seg": seg, "t": e["t"], "triggers": set(e.get("triggers", [])),
                                   "changes": e["changes"], "fields": _fields(e["changes"]),
                                   "before": before, "after": current, "claimed": False})
            else:
                continue
            times, states = self.points.setdefault(seg, ([], []))
            times.append(e["t"])
            states.append(current)

    def at(self, seg, t):
        times, states = self.points.get(seg, ([], []))
        i = bisect.bisect_right(times, t) - 1
        if states:
            return states[max(i, 0)]
        return {"mode": "OBJECT", "active": None, "selected": [], "objects": []}

    def claim(self, seg, t, trigger):
        for d in self.diffs:
            if (d["seg"] == seg and not d.get("resume") and not d["claimed"] and trigger in d["triggers"]
                    and t - 0.05 <= d["t"] <= t + UNDO_WINDOW):
                d["claimed"] = True
                d["event_t"] = t
                return d
        return None


def generate(actions, states):
    """actions/states: journal entries (headers removed), in file order."""
    st = _States(states)
    elements = []   # (seg, t, order, element); element is an Item or an event dict
    ignored = []
    seen = set()
    mode = "OBJECT"
    pause_at = None
    order = 0

    def add(seg, t, element):
        nonlocal order
        elements.append((seg, t, order, element))
        order += 1

    for seg, e in _segment(actions, ("start", "recovered")):
        kind, t = e.get("kind"), e.get("t", 0.0)
        if kind in ("start", "recovered"):
            mode = st.at(seg, t)["mode"]
            if kind == "recovered":
                add(seg, t, Item(REVIEW, "event", "Recording continued after Blender closed without stopping",
                                 seg, t, reason="Work done after the last saved entry may be missing; "
                                                "check the scene matches the steps around here.",
                                 evidence=[f"recovered in Blender {e.get('blender', '?')}"]))
                add(seg, t, {"event": "reset"})
        elif kind == "report":
            key = (e.get("bs"), e.get("uid"))
            if key in seen:
                continue
            seen.add(key)
            item = _report_item(seg, t, e, st.at(seg, t), mode, ignored)
            if item is not None:
                if item.op == "object.editmode_toggle":
                    mode = "OBJECT" if mode.startswith("EDIT") else "EDIT"
                elif item.op == "object.mode_set" and "mode" in item.args:
                    mode = "OBJECT" if item.args["mode"] == "OBJECT" else str(item.args["mode"])
                add(seg, t, item)
        elif kind in ("undo", "redo"):
            d = st.claim(seg, t, kind)
            if d and "mode" in d["changes"]:
                mode = d["changes"]["mode"]
            add(seg, t, {"event": kind, "diff": d})
        elif kind == "pause":
            pause_at = (seg, t)
        elif kind == "resume":
            if pause_at and pause_at[0] == seg:
                resumed = next((d for d in st.diffs if d.get("resume") and d["seg"] == seg and d["t"] == t), None)
                if resumed and resumed["before"] and resumed["before"] != resumed["after"]:
                    changes = diff_states(resumed["before"], resumed["after"])
                    summary = _state_title({k: _value(resumed["after"], k) for k in _fields(changes)})
                    ignored.append(Ignored(seg, t, "changed while recording was paused", summary))
                mode = st.at(seg, t)["mode"]
            pause_at = None
        elif kind == "file_loaded":
            d = st.claim(seg, t, "load")
            mode = (d["after"] if d else st.at(seg, t + UNDO_WINDOW))["mode"]
            add(seg, t, Item(REVIEW, "event", f"Opened file {e.get('file') or '(unsaved)'}", seg, t,
                             reason="Lessons cannot open files; check whether later steps rely on this file."))
            add(seg, t, {"event": "reset"})

    reports = [el for el in elements if isinstance(el[3], Item) and el[3].kind == "action"]
    for d in st.diffs:
        if d.get("resume"):
            continue
        # A diff taken after an undo, redo or file load belongs to that event, except
        # what a report made after the event explains (one diff can cover both).
        after_event = d.get("event_t") if d["claimed"] else None
        if after_event is None and d["triggers"] & {"undo", "redo", "load"}:
            after_event = d["t"] - EXPLAIN_BEFORE
        unexplained = {}
        for key in d["fields"]:
            owner = _explainer(reports, d, key[1], after_event)
            if owner is not None:
                owner.changes[key] = _value(d["after"], key)
            elif after_event is None:
                unexplained[key] = _value(d["after"], key)
        if not unexplained:
            continue
        before = {k: _value(d["before"], k) for k in unexplained}
        names = {n for _, n in unexplained}
        if names <= SELECTION:
            add(d["seg"], d["t"], {"event": "selection", "affects": SELECTION, "changes": unexplained})
            continue
        add(d["seg"], d["t"], Item(DRAFT, "state", _state_title(unexplained), d["seg"], d["t"],
                                   objects=sorted({o for o, _ in unexplained if o}), changes=unexplained,
                                   affects=frozenset(names), before=before,
                                   evidence=["state change with no matching action report"]))

    elements.sort(key=lambda el: el[:3])
    _merge_state_items(elements, ignored)
    _apply_undo(elements, ignored)
    _collapse_properties(elements, ignored)

    items = []
    for seg, t, _, el in elements:
        if isinstance(el, Item) and not el.dropped:
            if el.op == "object.editmode_toggle" and ("", "mode") in el.changes:
                el.title = "Leave Edit Mode" if el.changes[("", "mode")] == "OBJECT" else "Enter Edit Mode"
            # The scene changes an action caused name its objects better than the
            # selection at report time, which can lag behind by up to a second.
            added = sorted(o for (o, n), v in el.changes.items() if n == "exists" and v is not None)
            changed = sorted({o for o, _ in el.changes if o})
            if el.kind == "action" and not el.op.startswith("bpy.") and (added or changed):
                el.objects = added or changed
            el.check_hints = _check_hints(el.changes)
            items.append(el)
    ignored.sort(key=lambda i: (i.segment, i.t))
    stats = {
        "reports": sum(1 for e in actions if e.get("kind") == "report"),
        "state_diffs": sum(1 for e in states if e.get("kind") == "diff"),
        "drafts": sum(1 for i in items if i.status == DRAFT),
        "review": sum(1 for i in items if i.status == REVIEW),
        "ignored": len(ignored),
    }
    return DraftResult(items, ignored, stats)


def _report_item(seg, t, e, state, mode, ignored):
    message = e.get("message", "")
    try:
        kind, op, args = parse_report(e.get("type"), message)
    except ReportParseError as exc:
        return Item(REVIEW, "action", "Unreadable action report", seg, t, reason=f"Could not read it ({exc}).",
                    evidence=[message], affects=ANY)
    edit = mode.startswith("EDIT")
    active = state.get("active")
    if kind == "property":
        if op.startswith(UI_PREFIXES):
            ignored.append(Ignored(seg, t, "interface only", message))
            return None
        m = _OBJECT_PATH.match(op)
        if m:
            obj = m.group("name") or active
            affects = next((f for pattern, f in PROPERTY_FIELDS if re.match(pattern, m.group("rest"))), None)
            if affects is not None:
                title = f"Set {_property_label(m.group('rest'))} of {obj} to {_num(args['value'])}"
                return Item(DRAFT, "action", title, seg, t, op=op, args=args, objects=[obj] if obj else [],
                            evidence=[message], affects=frozenset(affects))
        m = _MATERIAL_PATH.match(op)
        if m:
            title = f"Set {_property_label(m.group('rest'))} of material {m.group('name')} to {_num(args['value'])}"
            return Item(DRAFT, "action", title, seg, t, op=op, args=args, evidence=[message], affects=frozenset())
        return Item(REVIEW, "action", f"Set {op}", seg, t, op=op, args=args, evidence=[message], affects=ANY,
                    reason="This property is not one the lesson format supports yet; write the step by hand.")
    m = re.match(r"mesh\.primitive_(\w+)_add$", op)
    if m:
        title = "Add " + _words(m.group(1)).title().replace("Uv ", "UV ")
        fields = {"dimensions"} if edit else EXISTENCE
    elif op in OPERATORS:
        title, fields = OPERATORS[op]
        title = _operator_title(op, args, title)
        if edit and op.startswith("transform."):
            fields = {"dimensions"}
    else:
        return Item(REVIEW, "action", f"Run {op}", seg, t, op=op, args=args, evidence=[message], affects=ANY,
                    reason="Unsupported tool (or an action from another add-on or a script); "
                           "write the step by hand or drop it.")
    objects = [active] if edit and active else list(state.get("selected", []))
    return Item(DRAFT, "action", title, seg, t, op=op, args=args, objects=objects, evidence=[message],
                affects=frozenset(fields))


def _explainer(reports, d, name, not_before=None):
    def affects(item):
        return item.affects is ANY or name in item.affects

    near = [el[3] for el in reports if el[0] == d["seg"] and d["t"] - EXPLAIN_BEFORE <= el[1] <= d["t"] + EXPLAIN_AFTER
            and affects(el[3]) and (not_before is None or el[1] >= not_before)]
    if near:
        return max(near, key=lambda i: i.t)
    later = [el[3] for el in reports if el[0] == d["seg"] and el[1] > d["t"] + EXPLAIN_AFTER]
    if not_before is None and later and later[0].t <= d["t"] + MODAL_LOOKAHEAD and affects(later[0]):
        return later[0]  # snapshot taken while an interactive tool was still running
    return None


def _merge_state_items(elements, ignored):
    """Rule 2 follow-up: back-to-back state drafts merge; a change undone by hand
    (e.g. a tool cancelled after the viewport updated) disappears."""
    previous = None
    for seg, t, _, el in elements:
        if isinstance(el, Item) and el.kind == "state":
            if previous is not None and previous.segment == seg and set(previous.objects) & set(el.objects):
                for key, v in el.changes.items():
                    previous.before.setdefault(key, el.before.get(key))
                    previous.changes[key] = v
                previous.affects = frozenset(previous.affects | el.affects)
                el.dropped = True
                el = previous
            el.title = _state_title(el.changes)
            if all(el.changes[k] == el.before.get(k) for k in el.changes):
                el.dropped = True
                ignored.append(Ignored(seg, t, "changed and changed back", el.title))
                previous = None
                continue
            previous = el
        elif not (isinstance(el, dict) and el["event"] == "selection"):
            previous = None


def _apply_undo(elements, ignored):
    live, redo = [], []

    def finalize():
        for el in redo:
            if isinstance(el, dict):  # selection change
                continue
            el.dropped = el.undo_match
            if el.undo_match:
                ignored.append(Ignored(el.segment, el.t, "undone", el.title))
            else:
                el.status = REVIEW
                el.reason = ((el.reason + " ") if el.reason else "") + \
                    "Probably undone, but the scene changes did not confirm which step the undo reverted."
        redo.clear()

    for seg, t, _, el in elements:
        if isinstance(el, Item) and el.dropped:
            continue
        if isinstance(el, dict) and el["event"] in ("undo", "redo"):
            d = el["diff"]
            if el["event"] == "undo":
                if not live:
                    ignored.append(Ignored(seg, t, "undo of work from before the recording (or not recorded)",
                                           "Undo with no recorded step before it"))
                    continue
                target = live.pop()
                affects = target["affects"] if isinstance(target, dict) else target.affects
                match = bool(d) and affects is not ANY and any(n in affects for _, n in d["fields"])
                if isinstance(target, dict):
                    target["undo_match"] = match
                else:
                    target.undo_match = match
                redo.append(target)
            elif redo:
                live.append(redo.pop())
            else:
                ignored.append(Ignored(seg, t, "redo with nothing recorded to redo", "Redo"))
        elif isinstance(el, dict) and el["event"] == "reset":
            finalize()
            live.clear()
        elif isinstance(el, dict) and el["event"] == "selection" or isinstance(el, Item) and el.kind != "event":
            finalize()
            live.append(el)
    finalize()


def _collapse_properties(elements, ignored):
    """Rule 1: repeated edits of one property, with nothing in between, keep the last value."""
    previous = None
    for seg, t, _, el in elements:
        if isinstance(el, Item) and el.dropped:
            continue
        if isinstance(el, Item) and el.kind == "action" and el.status == DRAFT and el.op.startswith("bpy."):
            if previous is not None and previous.op == el.op and previous.objects == el.objects:
                previous.dropped = True
                ignored.append(Ignored(previous.segment, previous.t, "replaced by a later value", previous.title))
                el.evidence = previous.evidence + el.evidence
                el.changes = {**previous.changes, **el.changes}
            previous = el
        elif isinstance(el, dict) and el["event"] == "selection":
            continue
        else:
            previous = None


def generate_from_folder(folder):
    """Read <folder>/actions.jsonl and state.jsonl and generate drafts."""
    _, actions, _ = read_journal(f"{folder}/actions.jsonl")
    _, states, _ = read_journal(f"{folder}/state.jsonl")
    return generate(actions, states)


# Output -------------------------------------------------------------------------------

def _when(item):
    return f"t={item.t:.1f}s" + (f" (session {item.segment + 1})" if item.segment else "")


def render_text(result, title="Draft steps"):
    s = result.stats
    lines = [title, "=" * len(title),
             f"{s['reports']} action reports, {s['state_diffs']} state changes -> "
             f"{s['drafts']} drafts, {s['review']} to review, {s['ignored']} not included", ""]
    for n, item in enumerate(result.items, 1):
        tag = "DRAFT " if item.status == DRAFT else "REVIEW"
        on = f" [{', '.join(item.objects)}]" if item.objects else ""
        lines.append(f"{n:3}. {tag} {item.title}{on}  {_when(item)}")
        if item.reason:
            lines.append(f"       why review: {item.reason}")
        for hint in item.check_hints:
            lines.append(f"       check: {hint}")
        for ev in item.evidence:
            lines.append(f"       from: {ev if len(ev) <= 160 else ev[:157] + '...'}")
    if result.ignored:
        lines += ["", "Not included", "------------"]
        for ig in result.ignored:
            text = ig.text if len(ig.text) <= 120 else ig.text[:117] + "..."
            lines.append(f"  t={ig.t:.1f}s  {ig.reason}: {text}")
    return "\n".join(lines) + "\n"


def to_json(result):
    def item(i):
        return {
            "status": i.status, "kind": i.kind, "title": i.title, "segment": i.segment, "t": i.t,
            "reason": i.reason, "op": i.op, "args": _round(i.args), "objects": i.objects, "evidence": i.evidence,
            "changes": [{"object": o, "field": n, "value": _round(v)} for (o, n), v in sorted(i.changes.items())],
            "check_hints": i.check_hints,
        }
    return {
        "stats": result.stats,
        "items": [item(i) for i in result.items],
        "ignored": [{"segment": i.segment, "t": i.t, "reason": i.reason, "text": i.text} for i in result.ignored],
    }
