"""data/*.json 으로 DESIGN.md 의 자동 생성 표(<!-- AUTO:START --> ~ <!-- AUTO:END -->)를 다시 만든다.
수치를 바꾼 뒤:  python tools/gen_design_tables.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.data import GameData  # noqa: E402

START, END = "<!-- AUTO:START -->", "<!-- AUTO:END -->"


def unlock(d, u):
    if not u:
        return "처음부터"
    k, _, v = u.partition(":")
    return d.eras[int(v)]["name"] if k == "era" else f"연구: {d.techs[v]['name']}"


def amounts(d, m):
    return ", ".join(f"{d.item_name(i)} {n}" for i, n in m.items())


def build(d):
    out = []
    out.append("### 1. 아이템\n")
    out.append("| ID | 이름 | 시대 | 판매가 | 연료(kJ) |\n|---|---|---|---|---|")
    for i in d.items.values():
        out.append(f"| `{i['id']}` | {i['name']} | T{i['tier']} | ${i['value']} | {i.get('fuel', '')} |")
    cats = {"smelter": "제련로", "assembler": "조립기", "refinery": "정유소", "chemical": "화학공장"}
    out.append("\n### 2. 레시피 (시간은 속도 1 기준)\n")
    out.append("| 레시피 | 재료 | 결과 | 시간(초) | 건물 | 해금 |\n|---|---|---|---|---|---|")
    for r in d.recipes.values():
        out.append(f"| {r['name']} | {amounts(d, r['inputs'])} | {amounts(d, r['outputs'])} | {r['time']} | {cats.get(r['category'], r['category'])} | {unlock(d, r.get('unlock'))} |")
    out.append("\n### 3. 건물\n")
    out.append("| 이름 | 분류 | 크기 | 비용 | 소비전력 | 주요 수치 | 해금 |\n|---|---|---|---|---|---|---|")
    cn = {c["id"]: c["name"] for c in d.categories}
    for b in d.buildings.values():
        stat = []
        for k, label in (("speed", "속도"), ("rate", "채굴/초"), ("output", "발전 kW"), ("reach", "연결 거리"),
                         ("long_reach", "장거리"), ("supply", "공급 반경"), ("capacity", "저장 kJ"), ("range", "지하 거리")):
            if b.get(k):
                stat.append(f"{label} {b[k]}")
        s = b.get("size", 1)
        out.append(f"| {b['name']} | {cn[b['category']]} | {s}x{s} | ${b['cost']:,} | {b.get('power', 0) or '-'} | {', '.join(stat) or '-'} | {unlock(d, b.get('unlock'))} |")
    out.append("\n### 4. 연구 트리\n")
    fn = {f["id"]: f["name"] for f in d.fields}
    out.append("| 연구 | 분야 | 시대 | 선행 | 연구팩(단위당 각 1) | 단위 | 단위 시간 | 효과 |\n|---|---|---|---|---|---|---|---|")
    for t in d.techs.values():
        pre = ", ".join(d.techs[p]["name"] for p in t["prereqs"]) or "-"
        packs = "+".join(d.item_name(p).replace(" 연구팩", "") for p in t["packs"])
        era = d.eras[t["era"]]["name"]
        rep = " (반복)" if t.get("repeatable") else ""
        out.append(f"| {t['name']}{rep} | {fn[t['field']]} | {era} | {pre} | {packs} | {t['units']} | {t['unit_time']}s | {t.get('desc', '')} |")
    out.append("\n### 5. 시대별 마일스톤 (누적 생산량)\n")
    out.append("| 시대 | 목표 | 설명 |\n|---|---|---|")
    for e in d.progression["eras"]:
        m = e.get("milestone")
        goal = amounts(d, m["produce"]) if m else ("메가 프로젝트 완성" if e["era"] == 6 else "-")
        out.append(f"| {e['name']} | {goal} | {e['desc']} |")
    out.append("\n### 6. 메가 프로젝트: 무인 스마트 팩토리 코어\n")
    out.append("| 단계 | 납품 품목 |\n|---|---|")
    for s in d.progression["megaproject"]["stages"]:
        out.append(f"| {s['name']} | {amounts(d, s['items'])} |")
    return "\n".join(out)


def main():
    path = os.path.join(ROOT, "DESIGN.md")
    text = open(path, encoding="utf-8").read()
    a, b = text.index(START) + len(START), text.index(END)
    text = text[:a] + "\n" + build(GameData()) + "\n" + text[b:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("DESIGN.md 표 갱신 완료")


if __name__ == "__main__":
    main()
