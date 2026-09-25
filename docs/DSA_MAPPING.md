| Feature | DSA Topic | C++ Operation | Time Complexity |
|---|---|---|---|
| Inventory statistics and resizing demo | Static array + dynamic vector traversal | `analyze_inventory` | `O(n)` |
| Configurable inventory sorting | Bubble/Insertion/Selection/Merge/Quick sort | `sort_blood_units` | `O(n^2)` worst, `O(n log n)` for merge/quick average |
| FEFO blood dispatch | Custom min-heap | `fefo_heap_dispatch` | Insert/Extract `O(log n)`, dump `O(n log n)` |
| Donor waiting queue | Singly linked list | `donor_queue_list` | Insert front `O(1)`, insert back/delete/traverse `O(n)` |
| Request history navigation | Doubly linked list | `request_history_list` | Insert `O(1)`, delete/search/traverse `O(n)` |
| Duty hospital scheduling | Circular linked list | `duty_rotation_circular` | `O(n * rotations)` |
| Pending request processor | Circular array queue | `process_request_queue` | Enqueue/Dequeue `O(1)` |
| Undo manager | Array stack | `undo_action_stack` | Push/Pop/Peek `O(1)` |
| Nearest blood source routing | Weighted graph + Dijkstra (custom heap) | `find_nearest_hospital` | `O((V+E) log V)` |
| Backup routing candidates | Graph BFS traversal | `bfs_backup_hospitals` | `O(V+E)` |
| Donor and blood lookup cache | Chained hash table | `hash_lookup` | Average `O(1)`, worst `O(n)` |
| Balanced donor index | AVL tree rotations/search | `avl_tree_operations` | Insert/Search `O(log n)` |
| Hierarchy traversal explorer | Binary tree traversals | `binary_tree_traversal` | Build `O(n)`, each traversal `O(n)` |
| Intake eligibility screening | Rule-engine array checks | `screen_donor` | `O(1)` (fixed rule count) |
| Compatibility resolution | Compatibility map + filtered sort | `match_blood_group` | Filter `O(n)`, sort `O(n^2)` (insertion sort) |
