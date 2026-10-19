"""Copy a reviewed four-sheet XLSX, changing explicit cell contents only.

The editing plan is prepared after comparing a completed report with source rows.
This tool preserves XML outside the edited cell fragments, including formulas,
styles, drawings, sheet names, merged cells, row heights and column dimensions.
It is not a row-insertion engine or a formula recalculation engine.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def sheet_parts(archive):
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {r.attrib["Id"]: r.attrib["Target"] for r in relationships}
    result = {}
    for sheet in workbook.find(f"{{{MAIN}}}sheets"):
        target = targets[sheet.attrib[f"{{{REL}}}id"]]
        result[sheet.attrib["name"]] = target.lstrip("/") if target.startswith("/") else "xl/" + target
    return result


def patch_cell(xml, edit):
    coordinate = edit["cell"]
    if not re.fullmatch(r"[A-Z]+[1-9]\d*", coordinate) or int(re.search(r"\d+", coordinate)[0]) <= 4:
        raise ValueError(f"Only detail cells after the header may be edited: {coordinate}")
    pattern = re.compile(r'<c\b(?=[^>]*\br="' + coordinate + r'")[^>]*(?:/>|>.*?</c>)', re.S)
    match = pattern.search(xml)
    if match is None:
        raise ValueError(f"Target cell is absent; prepare a reviewed layout first: {coordinate}")
    old_fragment = match.group()
    element = ET.fromstring(old_fragment)
    attributes = dict(element.attrib)
    attributes.pop("t", None)
    kind, value = edit["type"], edit.get("value")
    if kind == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError(f"Expected a numeric value: {coordinate}")
        if element.find("f") is not None:
            raise ValueError(f"Refusing to overwrite an existing formula: {coordinate}")
        payload = f"<v>{value}</v>"
    elif kind == "text":
        if element.find("f") is not None:
            raise ValueError(f"Refusing to overwrite an existing formula: {coordinate}")
        attributes["t"] = "inlineStr"
        payload = '<is><t xml:space="preserve">' + escape(str(value)) + "</t></is>"
    elif kind == "formula_cache":
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError(f"Expected a numeric formula cache: {coordinate}")
        formula = re.search(r"<f(?:\s[^>]*)?>.*?</f>", old_fragment, re.S)
        if formula is None:
            raise ValueError(f"No original formula to preserve: {coordinate}")
        payload = formula.group() + f"<v>{value}</v>"
    else:
        raise ValueError(f"Unsupported content edit: {kind}")
    new_fragment = "<c " + " ".join(k + "=" + quoteattr(v) for k, v in attributes.items()) + ">" + payload + "</c>"
    return xml[:match.start()] + new_fragment + xml[match.end():]


def apply(plan, output):
    template = Path(plan["template"]).resolve(strict=True)
    output = Path(output).resolve()
    roots = [template.parent] + [Path(p).resolve() for p in plan.get("source_roots", [])]
    if any(output.is_relative_to(root) for root in roots):
        raise ValueError("Output must be outside source directories")
    if output.exists():
        raise FileExistsError(output)
    original_sha = hashlib.sha256(template.read_bytes()).hexdigest()
    if original_sha != plan["template_sha256"]:
        raise ValueError("Template changed since the editing plan was prepared")
    for source in plan.get("sources", []):
        if hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Source changed since review: {source['path']}")
    seen = set()
    with ZipFile(template) as source:
        parts = sheet_parts(source)
        names = list(parts)
        if len(names) != 4:
            raise ValueError("Expected the reviewed four-sheet summary template")
        allowed = set(names[1:3])
        changed = {}
        for edit in plan["edits"]:
            if edit["sheet"] not in allowed:
                raise ValueError("Only sheets 2 and 3 can be edited")
            key = (edit["sheet"], edit["cell"])
            if key in seen:
                raise ValueError(f"Cell selected twice: {key}")
            seen.add(key)
            part = parts[edit["sheet"]]
            xml = changed.get(part, source.read(part).decode("utf-8"))
            changed[part] = patch_cell(xml, edit)
        # Validate every patch before creating the output.
        for xml in changed.values():
            ET.fromstring(xml)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as handle, ZipFile(handle, "w") as destination:
            for info in source.infolist():
                content = changed[info.filename].encode("utf-8") if info.filename in changed else source.read(info.filename)
                destination.writestr(deepcopy(info), content)
            destination.comment = source.comment
    if hashlib.sha256(template.read_bytes()).hexdigest() != original_sha:
        raise RuntimeError("Source template changed while copying")
    return {"output": str(output), "edits": len(seen), "changed_parts": sorted(changed),
            "protected_sheets": [names[0], names[3]], "template_unchanged": True,
            "recalculation": "Original formulas preserved; edited caches checked separately, not engine recalculation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = apply(json.loads(args.plan.read_text(encoding="utf-8-sig")), args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
