"""data/ 폴더 JSON 로더. 새 콘텐츠는 JSON만 추가하면 되도록 모든 정의를 여기서 읽고 검증한다."""
import json

from .paths import resource_path


class DataError(Exception):
    pass


def _load(name):
    path = resource_path("data", name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise DataError(f"데이터 파일이 없습니다: {path}")
    except json.JSONDecodeError as e:
        raise DataError(f"{name} JSON 문법 오류: {e}")


class GameData:
    def __init__(self):
        items = _load("items.json")["items"]
        self.items = {i["id"]: i for i in items}
        self.item_order = [i["id"] for i in items]
        self.recipes = {r["id"]: r for r in _load("recipes.json")["recipes"]}
        b = _load("buildings.json")
        self.categories = b["categories"]
        self.buildings = {x["id"]: x for x in b["buildings"]}
        t = _load("tech.json")
        self.fields = t["fields"]
        self.techs = {x["id"]: x for x in t["techs"]}
        self.progression = _load("progression.json")
        self.eras = {e["era"]: e for e in self.progression["eras"]}
        self.fuels = {k: v["fuel"] for k, v in self.items.items() if "fuel" in v}
        self._validate()

    # ---- 검증: 오타가 있으면 게임 시작 시 바로 알려준다 ----
    def _validate(self):
        errs = []

        def chk_item(i, where):
            if i not in self.items:
                errs.append(f"{where}: 알 수 없는 아이템 '{i}'")

        def chk_unlock(u, where):
            if u is None:
                return
            kind, _, val = u.partition(":")
            if kind == "tech" and val not in self.techs:
                errs.append(f"{where}: 알 수 없는 연구 '{val}'")
            elif kind == "era" and not val.isdigit():
                errs.append(f"{where}: 잘못된 era '{u}'")
            elif kind not in ("tech", "era"):
                errs.append(f"{where}: unlock 형식 오류 '{u}'")

        for r in self.recipes.values():
            for i in list(r["inputs"]) + list(r["outputs"]):
                chk_item(i, f"recipe {r['id']}")
            chk_unlock(r.get("unlock"), f"recipe {r['id']}")
        cats = {c["id"] for c in self.categories}
        for b in self.buildings.values():
            chk_unlock(b.get("unlock"), f"building {b['id']}")
            if b["category"] not in cats:
                errs.append(f"building {b['id']}: 카테고리 '{b['category']}' 없음")
            for f in b.get("fuels", {}):
                chk_item(f, f"building {b['id']} fuels")
        for t in self.techs.values():
            for p in t["prereqs"]:
                if p not in self.techs:
                    errs.append(f"tech {t['id']}: 선행 연구 '{p}' 없음")
            for p in t["packs"]:
                chk_item(p, f"tech {t['id']}")
        for e in self.progression["eras"]:
            if e.get("milestone"):
                for i in e["milestone"]["produce"]:
                    chk_item(i, f"era {e['era']} milestone")
        for s in self.progression["megaproject"]["stages"]:
            for i in s["items"]:
                chk_item(i, "megaproject")
        if errs:
            raise DataError("데이터 오류:\n" + "\n".join(errs))

    def item_name(self, iid):
        return self.items[iid]["name"] if iid in self.items else iid

    def recipes_for(self, category):
        return [r for r in self.recipes.values() if r["category"] == category]
