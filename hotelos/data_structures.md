# Data structure choices

- `rooms` (list/array): simple ordered collection of 10 rooms. Efficient for iteration and small fixed-size set.
- `guests` (dict/map): keyed by guest id for O(1) lookup, needed to find guest records quickly during checkout.
- `maintenance` (priority queue using `heapq`): issues have urgency levels; heap provides efficient retrieval of highest priority (lowest "urgency" number).
- `room service orders` (asyncio.Queue + dict): queue models FIFO processing; dict maintains orders by id for state updates and lookups.

These choices match the required semantics: fast lookup for guests, priority handling for maintenance, FIFO for orders, and a straightforward list for room inventory.
