# import json
# from pathlib import Path
#
# path = Path("assets/officer_names.json")
#
# with path.open("r", encoding="utf-8") as f:
#     data = json.load(f)
#
# # Sort by integer id
# data.sort(key=lambda obj: int(obj["id"]))
#
# # Write back to the same file
# with path.open("w", encoding="utf-8") as f:
#     json.dump(data, f, indent=2, ensure_ascii=False)