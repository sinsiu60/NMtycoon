"""세이브/로드. 내 문서/FactoryTycoon/slotN.json 에 JSON으로 저장."""
import json
import os
import time

from .game import Game
from .paths import save_dir

SAVE_VERSION = 1
SLOTS = (1, 2, 3)


def slot_path(slot):
    return os.path.join(save_dir(), f"slot{slot}.json")


def serialize(game):
    bs = []
    for b in game.buildings.values():
        e = {"uid": b.uid, "type": b.type, "x": b.x, "y": b.y, "dir": b.dir}
        if b.invert:
            e["invert"] = True
        if b.priority != 1:
            e["priority"] = b.priority
        st = b.save_state()
        if st:
            e["state"] = st
        bs.append(e)
    return {
        "version": SAVE_VERSION,
        "saved_at": time.time(),
        "seed": game.seed,
        "money": game.money,
        "era": game.era,
        "time": game.time,
        "play_time": game.play_time,
        "next_uid": game.next_uid,
        "stats_produced": game.stats_produced,
        "stats_sold": game.stats_sold,
        "total_earned": game.total_earned,
        "research": game.research.to_dict(),
        "progress": game.progress.to_dict(),
        "links": game.control.links,
        "tripped_poles": [p.uid for n in game.power.nets if n.tripped for p in n.poles],
        "buildings": bs,
    }


def deserialize(data, d):
    from . import buildings as B
    g = Game(data, seed=d["seed"])
    g.money = d.get("money", 0)
    g.era = d.get("era", 1)
    g.time = d.get("time", 0.0)
    g.play_time = d.get("play_time", 0.0)
    g.stats_produced = dict(d.get("stats_produced", {}))
    g.stats_sold = dict(d.get("stats_sold", {}))
    g.total_earned = d.get("total_earned", 0)
    g.research.load(d.get("research", {}))
    g.progress.load(d.get("progress", {}))
    max_uid = 0
    for e in d.get("buildings", []):
        defn = data.buildings.get(e["type"])
        if defn is None:
            continue
        b = B.create(g, defn, e["x"], e["y"], e["dir"])
        b.uid = e["uid"]
        b.invert = e.get("invert", False)
        b.priority = e.get("priority", 1)
        try:
            b.load_state(e.get("state", {}))
        except Exception:
            pass
        if any(not g.world.in_bounds(tx, ty) or g.world.at(tx, ty) for tx, ty in b.tiles()):
            continue
        g._add(b)
        max_uid = max(max_uid, b.uid)
    g.next_uid = max(d.get("next_uid", 1), max_uid + 1)
    g.control.links = [l for l in d.get("links", []) if l["src"] in g.buildings and l["dst"] in g.buildings]
    g.power.rebuild()
    tripped = set(d.get("tripped_poles", []))
    for n in g.power.nets:
        if any(p.uid in tripped for p in n.poles):
            n.tripped = True
    return g


def save_game(game, slot):
    path = slot_path(slot)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(serialize(game), f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)
    game.slot = slot
    return path


def load_game(data, slot):
    with open(slot_path(slot), encoding="utf-8") as f:
        d = json.load(f)
    g = deserialize(data, d)
    g.slot = slot
    return g


def slot_info(slot):
    """슬롯 요약 (없으면 None)."""
    p = slot_path(slot)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return {"era": d.get("era", 1), "money": d.get("money", 0), "play_time": d.get("play_time", 0),
                "saved_at": d.get("saved_at", os.path.getmtime(p))}
    except Exception:
        return {"broken": True}


SETTINGS_DEFAULT = {"volume": 0.6, "autosave": True, "show_grid": True}


def load_settings():
    p = os.path.join(save_dir(), "settings.json")
    s = dict(SETTINGS_DEFAULT)
    try:
        with open(p, encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s


def save_settings(s):
    try:
        with open(os.path.join(save_dir(), "settings.json"), "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=1)
    except OSError:
        pass
