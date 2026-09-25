# LIFELINE: Intelligent Blood Logistics Network
**Author:** <Student Name Here>  
**Department:** Computer Science  
**Date:** June 2026

## Abstract
LIFELINE is a university capstone project that applies core data structures and algorithms to a real-world emergency blood logistics workflow. The system is intentionally split into two layers: a Streamlit interface for user interaction and a C++ computational engine for all algorithmic processing. This separation enforces clean architecture while demonstrating practical deployment constraints in offline hospital environments. The solution supports donor screening, inventory analysis, FEFO dispatch, request queue handling, emergency graph routing, and blood compatibility matching. Each major feature maps to a specific DSA topic, including linked lists, heaps, stacks, queues, hash tables, AVL trees, binary tree traversal, BFS, and Dijkstra. The project satisfies curricular outcomes by combining algorithm design rigor with production-style integration, input validation, and reproducible operational workflows.

## 1. Introduction
Emergency blood access depends on speed, correctness, and transparency. Manual inventory coordination can delay life-saving treatment and create avoidable shortages or wastage. LIFELINE was designed to demonstrate how classical DSA concepts can directly improve hospital decision support for blood operations.

The project follows an offline-first architecture to remain practical in environments with inconsistent network reliability. SQLite provides local persistence, Streamlit provides rapid UI delivery, and the C++ engine executes all computational logic through a strict JSON subprocess contract.

## 2. System Architecture
LIFELINE is built around the principle: **Python is the interface, C++ is the algorithmic core.**

1. Streamlit pages collect user inputs and display charts/tables.
2. Python sends operation requests as JSON to `dsa_engine.exe`.
3. C++ executes operation-specific data structure/algorithm logic.
4. C++ returns structured JSON responses.
5. Python renders results and persists approved records to SQLite.

### Architecture Diagram (Text)
`User -> Streamlit UI -> Python Bridge (subprocess) -> C++ DSA Engine -> JSON Response -> UI + SQLite`

## 3. DSA Implementation Details

### 3.1 analyze_inventory
Uses static arrays and dynamic vector migration to compute total, min, max, and average quantities while demonstrating capacity doubling.

### 3.2 sort_blood_units
Implements Bubble, Insertion, Selection, Merge, and Quick sort; records comparisons/swaps for pedagogical analysis.

### 3.3 fefo_heap_dispatch
Custom min-heap keyed by expiry date enables FEFO dispatch to reduce near-expiry waste.

### 3.4 donor_queue_list
Singly linked list simulates donor registration queue operations with pointer-level insertion/deletion.

### 3.5 request_history_list
Doubly linked list supports forward and backward traversal of historical requests.

### 3.6 duty_rotation_circular
Circular linked list rotates active duty hospitals for emergency coordination.

### 3.7 process_request_queue
Array-based circular queue ensures FIFO processing of blood requests.

### 3.8 undo_action_stack
Array-based stack stores reversible actions for safe user operations.

### 3.9 find_nearest_hospital
Weighted graph with Dijkstra identifies shortest path to the nearest hospital with required blood availability.

### 3.10 bfs_backup_hospitals
BFS traversal discovers alternative hospitals in layer order for escalation fallback.

### 3.11 hash_lookup
Custom chained hash table provides expected constant-time donor and blood-group lookup.

### 3.12 avl_tree_operations
Self-balancing AVL tree ensures logarithmic donor indexing and deterministic rotation reporting.

### 3.13 binary_tree_traversal
Builds a complete binary tree and demonstrates inorder, preorder, and postorder traversals.

### 3.14 screen_donor
Rule-engine style evaluation applies medically relevant constraints and returns `eligible`, `caution`, or `rejected`.

### 3.15 match_blood_group
Compatibility mapping with quantity-aware filtering returns safe transfusion candidates and low-stock alerts.

## 4. CLO Mapping Table
| CLO | Evidence in LIFELINE |
|---|---|
| CLO-1: Design and implement DSA solutions | 15 independent operations implemented in C++ with custom structures and algorithm dispatch |
| CLO-3: Apply DSA to real-world problems | Hospital routing, donor screening, inventory dispatch, and queue-based request processing |

## 5. Conclusion
LIFELINE demonstrates that DSA topics are not isolated academic exercises; they are directly applicable to critical healthcare workflows. By separating UI from algorithmic computation, the project remains maintainable, testable, and academically defensible. The final result is a practical offline system and a complete educational showcase of algorithm selection under real operational constraints.

## 6. References
1. Cormen, T. H., Leiserson, C. E., Rivest, R. L., and Stein, C. *Introduction to Algorithms* (3rd ed.). MIT Press.
2. Goodrich, M. T., Tamassia, R., and Goldwasser, M. H. *Data Structures and Algorithms in C++*. Wiley.
3. Sedgewick, R., and Wayne, K. *Algorithms* (4th ed.). Addison-Wesley.
