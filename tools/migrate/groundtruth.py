"""Ground-truth store. In-game dumps win over db2 on conflict (spec §4)."""
import csv
import json
import pathlib


class GroundTruth:
    def __init__(self, ingame: dict, db2_names: dict):
        self._ingame = {int(k): v for k, v in ingame.items()}
        self._db2 = {int(k): v for k, v in db2_names.items()}
        self._by_name: dict = {}
        for sid, rec in self._db2.items():
            self._by_name.setdefault(rec["name"], []).append(sid)
        for sid, rec in self._ingame.items():
            ids = self._by_name.setdefault(rec["name"], [])
            if sid not in ids:
                ids.append(sid)

    @classmethod
    def load(cls, gt_dir) -> "GroundTruth":
        gt_dir = pathlib.Path(gt_dir)
        ingame = {}
        spells_json = gt_dir / "spells.json"
        if spells_json.exists():
            ingame = json.loads(spells_json.read_text())
        db2_names = {}
        csv_path = gt_dir / "db2" / "SpellName.csv"
        if csv_path.exists():
            with csv_path.open(newline="") as f:
                for row in csv.DictReader(f):
                    db2_names[row["ID"]] = {"name": row["Name_lang"]}
        if not ingame and not db2_names:
            raise FileNotFoundError(
                f"no ground truth in {gt_dir} — run /xdump in-game + wa pull-groundtruth, "
                f"and/or tools/migrate/fetch_db2.py")
        return cls(ingame, db2_names)

    def spell_by_id(self, spell_id: int):
        return self._ingame.get(spell_id) or self._db2.get(spell_id)

    def ids_by_name(self, name: str):
        return self._by_name.get(name, [])

    def source_of(self, spell_id: int):
        if spell_id in self._ingame:
            return "ingame"
        if spell_id in self._db2:
            return "db2"
        return None
