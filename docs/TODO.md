Tracks:
- Growth
    - Twitter posts and outreach
    - Every day pick one library, see what Archie says about it, and publish it

    - Comparable benchmarking: e.g. run a feature request with Archie and without — record token count and time for each. (CSACSI)

    - How to start a project from a blueprint — in the share view let users say "I want to work this way"

    - Two levels of blueprint: for humans, the connection to the product so they know what's happening in the app; for agents, the rules

    Quick tasks:
    - Should the AI also generate the diagram? Is that a problem?
    - Code-quality metrics are meaningless: move them to the end for anyone who cares

- Engineering
   - Deep scan is slow (HAMU)
        - Separate Risk Agent (parallel agents)
        - Make it more predictable and faster
        - Scriptify it
        - Restructure the drift logic
        - The "necessary but not sufficient" problem — false positives / false negatives in the findings

   - Reasoning agent is weak — what goes where, what the architecture looks like — generate rules for this -> Use the blueprint on a fresh project (CSACSI)

   - Rethink indexing

   - Review the semantic-emptiness implementation: vector-compare the function list to find which ones might be the same

   - Rethink what scan should actually do

Future:
- Add future-forwarding decisions into the blueprint
- Blueprint on GitHub
- Handling multi-repo setups (POC)
