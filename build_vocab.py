# -*- coding: utf-8 -*-
"""Merge vocab_a1/a2/b1/b2 into course_data.json under a top-level 'vocabulary' key."""
import json
import vocab_a1, vocab_a2, vocab_b1, vocab_b2

LEVELS = [("A1", vocab_a1.CATEGORIES), ("A2", vocab_a2.CATEGORIES), ("B1", vocab_b1.CATEGORIES), ("B2", vocab_b2.CATEGORIES)]

def build():
    vocab = {}
    total = 0
    seen_global = set()
    for code, cats in LEVELS:
        words_flat = []
        cat_out = []
        seen_level = set()
        for cat in cats:
            w_out = []
            for (de, pos, en, ex_de, ex_en) in cat["words"]:
                key = de.strip().lower()
                if key in seen_level:
                    print("DUPLICATE within level %s: %r" % (code, de))
                seen_level.add(key)
                entry = {"de": de, "pos": pos, "en": en, "ex_de": ex_de, "ex_en": ex_en}
                w_out.append(entry)
                words_flat.append(entry)
            cat_out.append({"name": cat["name"], "icon": cat["icon"], "words": w_out})
        vocab[code] = {"categories": cat_out, "count": len(words_flat)}
        total += len(words_flat)
        print("%s: %d categories, %d words" % (code, len(cat_out), len(words_flat)))

    with open("course_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    data["vocabulary"] = vocab

    with open("course_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    print("TOTAL vocab words:", total)
    import os
    print("course_data.json size KB:", round(os.path.getsize("course_data.json") / 1024, 1))

if __name__ == "__main__":
    build()
