from collections import Counter

def inspect_pages(values: list[str], expected_count: int) -> dict:
    numbers = [int(value) for value in values]
    counts = Counter(numbers)
    expected = set(range(1, expected_count + 1))
    present = set(numbers)
    return {"missing": sorted(expected - present), "duplicates": sorted(n for n, count in counts.items() if count > 1), "unexpected": sorted(present - expected)}

def inspect_by_volume(pages: list[dict], plans: list[dict]) -> dict:
    """按分卷版号独立验页。

    plans: [{"edition": "01A", "expected_pages": 4}, ...]，来自期版修订。
    pages: 已采纳的扫描行，需带 edition/page/version/clarity。
    每卷单独择版、单独对期望页集合验缺页；缺页不会被另一卷的同页码掩盖。
    """
    selected_by_edition: dict[str, list[dict]] = {}
    for row in pages:
        selected_by_edition.setdefault(row["edition"], []).append(row)

    volumes, all_complete = [], True
    for plan in plans:
        edition = plan["edition"]
        selected = select_versions(selected_by_edition.get(edition, []))
        status = inspect_pages([row["page"] for row in selected], plan["expected_pages"])
        complete = not status["missing"] and not status["unexpected"] and not status["duplicates"]
        all_complete = all_complete and complete
        volumes.append({
            "edition": edition,
            "expected_pages": plan["expected_pages"],
            "selected": selected,
            "input": len(selected_by_edition.get(edition, [])),
            "accepted": len(selected),
            "superseded": len(selected_by_edition.get(edition, [])) - len(selected),
            "missing": status["missing"],
            "duplicates": status["duplicates"],
            "unexpected": status["unexpected"],
            "complete": complete,
        })

    planned = {plan["edition"] for plan in plans}
    unknown_editions = sorted(edition for edition in selected_by_edition if edition not in planned)
    return {
        "volumes": volumes,
        "unexpected_editions": unknown_editions,
        "complete": all_complete and not unknown_editions,
    }

def select_versions(rows: list[dict]) -> list[dict]:
    selected = {}
    for row in rows:
        page = row["page"]
        score = (int(row.get("version", 0)), int(row.get("clarity", 0)), str(row.get("file_name", "")))
        current = selected.get(page)
        if current is None or score > current[0]:
            selected[page] = (score, row)
    return [selected[key][1] for key in sorted(selected, key=int)]

