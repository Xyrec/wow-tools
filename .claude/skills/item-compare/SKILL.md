---
name: item-compare
description: Compare two items side-by-side showing stat differences
---

Compare two WoW items by their item IDs. If the user did not provide two item IDs as arguments, ask: "Which two item IDs would you like to compare?"

Parse the arguments to extract two numeric item IDs. They may be provided as:

- Two space-separated numbers: "29028 29035"
- With a "vs" separator: "29028 vs 29035"

Run the command:

```
target/release/wow-tools lookup --compare {id1} {id2}
```

Present the results clearly, highlighting:

- Which stats one item has over the other (gains and losses)
- The net trade-off in plain language (e.g. "You trade 15 healing power for 10 mp5")
- A recommendation on which is better for the relevant spec if the context makes it clear
