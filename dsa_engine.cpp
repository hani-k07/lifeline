#include <iostream>
#include <vector>
#include <queue>
#include <unordered_map>
#include <string>
#include <memory>
#include <limits>
#include <algorithm>
#include <functional>
#include <nlohmann/json.hpp>

using json = nlohmann::json;
using namespace std;

// ==========================================
// 1. Dijkstra’s Algorithm (Graphs)
// ==========================================

/*
 * Algorithm: Dijkstra's Shortest Path
 * 
 * Time Complexity: O((V + E) log V)
 *   where V is the number of vertices (hospitals) and E is the number of edges (connections).
 *   The priority queue operations take logarithmic time.
 * Space Complexity: O(V + E)
 *   for storing the adjacency list graph and O(V) for distances and the priority queue.
 */
json findShortestPath(const json& graphData, const string& startNode, const string& targetNode) {
    // Build adjacency list
    unordered_map<string, vector<pair<string, int>>> adjList;
    for (const auto& edge : graphData) {
        string u = edge["source"];
        string v = edge["target"];
        int weight = edge["weight"];
        adjList[u].push_back({v, weight});
        adjList[v].push_back({u, weight}); // Assuming undirected graph for roads
    }

    // Min-heap for Dijkstra: pair<distance, node>
    priority_queue<pair<int, string>, vector<pair<int, string>>, greater<pair<int, string>>> pq;
    unordered_map<string, int> distances;
    unordered_map<string, string> previous;

    // Initialize distances to infinity
    for (const auto& pair : adjList) {
        distances[pair.first] = numeric_limits<int>::max();
    }
    
    distances[startNode] = 0;
    pq.push({0, startNode});

    while (!pq.empty()) {
        auto [currentDist, u] = pq.top();
        pq.pop();

        if (currentDist > distances[u]) continue;

        if (u == targetNode) break;

        for (const auto& neighbor : adjList[u]) {
            string v = neighbor.first;
            int weight = neighbor.second;

            // Compute potential new distance
            int newDist = distances[u] + weight;
            
            // If v is not in distances, it defaults to 0 without initialization,
            // so we must ensure it's initialized to infinity if not visited
            if (distances.find(v) == distances.end()) {
                distances[v] = numeric_limits<int>::max();
            }

            if (newDist < distances[v]) {
                distances[v] = newDist;
                previous[v] = u;
                pq.push({distances[v], v});
            }
        }
    }

    // Reconstruct path
    vector<string> path;
    if (distances.find(targetNode) != distances.end() && distances[targetNode] != numeric_limits<int>::max()) {
        string curr = targetNode;
        while (curr != startNode) {
            path.push_back(curr);
            curr = previous[curr];
        }
        path.push_back(startNode);
        reverse(path.begin(), path.end());
    }

    json result;
    result["path"] = path;
    result["distance"] = (path.empty()) ? -1 : distances[targetNode];
    return result;
}

// ==========================================
// 2. Breadth-First Search (Graphs)
// ==========================================

/*
 * Algorithm: Breadth-First Search (BFS) for nearest backup hospital
 * 
 * Time Complexity: O(V + E)
 *   where V is the number of hospitals and E is the number of connections. In the worst case, 
 *   we visit every hospital and edge once.
 * Space Complexity: O(V)
 *   for the queue, visited set, and adjacency list if passed by reference.
 */
json findNearestBackupHospital(const json& graphData, const json& inventoryData, const string& startNode, const string& requiredBloodType) {
    // Build adjacency list
    unordered_map<string, vector<string>> adjList;
    for (const auto& edge : graphData) {
        string u = edge["source"];
        string v = edge["target"];
        adjList[u].push_back(v);
        adjList[v].push_back(u); 
    }

    // Inventory map: maps hospital ID to a list of available blood types
    unordered_map<string, vector<string>> hospitalInventory;
    for (const auto& item : inventoryData) {
        hospitalInventory[item["hospitalId"]].push_back(item["bloodType"]);
    }

    queue<pair<string, int>> q; // {node, level/distance}
    unordered_map<string, bool> visited;

    q.push({startNode, 0});
    visited[startNode] = true;

    while (!q.empty()) {
        auto [u, dist] = q.front();
        q.pop();

        // Check if this hospital has the required blood type (skip start node)
        if (u != startNode) {
            const auto& inv = hospitalInventory[u];
            if (find(inv.begin(), inv.end(), requiredBloodType) != inv.end()) {
                json result;
                result["hospital"] = u;
                result["distanceLevel"] = dist;
                return result;
            }
        }

        for (const string& v : adjList[u]) {
            if (!visited[v]) {
                visited[v] = true;
                q.push({v, dist + 1});
            }
        }
    }

    json result;
    result["hospital"] = nullptr;
    return result;
}

// ==========================================
// 3. Min-Heap / Priority Queue (Heaps)
// ==========================================

struct BloodUnit {
    string id;
    string bloodType;
    long long expiryTimestamp;

    // Min-Heap comparator (FEFO - smallest timestamp first)
    bool operator>(const BloodUnit& other) const {
        return expiryTimestamp > other.expiryTimestamp;
    }
};

/*
 * Algorithm: Min-Heap for First-Expire-First-Out (FEFO) Blood Unit retrieval
 * 
 * Time Complexity: 
 *   - Insertion: O(log N) per unit
 *   - Retrieval/Top: O(1)
 *   - Extraction/Pop: O(log N) per unit
 *   - Overall for processing N units: O(N log N)
 * Space Complexity: O(N)
 *   where N is the number of blood units stored in the heap.
 */
json processFEFO(const json& bloodUnits) {
    priority_queue<BloodUnit, vector<BloodUnit>, greater<BloodUnit>> minHeap;

    for (const auto& unit : bloodUnits) {
        minHeap.push({
            unit["id"],
            unit["bloodType"],
            unit["expiryTimestamp"]
        });
    }

    json sortedUnits = json::array();
    while (!minHeap.empty()) {
        BloodUnit topUnit = minHeap.top();
        minHeap.pop();
        sortedUnits.push_back({
            {"id", topUnit.id},
            {"bloodType", topUnit.bloodType},
            {"expiryTimestamp", topUnit.expiryTimestamp}
        });
    }

    return sortedUnits;
}

// ==========================================
// 4. Merge Sort (Divide & Conquer)
// ==========================================

struct Contract {
    string contractId;
    string hospitalId;
    long long deadlineTimestamp;
};

/*
 * Algorithm: Merge step of Merge Sort
 * 
 * Time Complexity: O(N)
 *   where N is the number of elements being merged (right - left + 1).
 * Space Complexity: O(N)
 *   for the temporary dynamic arrays used during merging.
 */
void mergeContracts(vector<Contract>& arr, int left, int mid, int right) {
    int n1 = mid - left + 1;
    int n2 = right - mid;

    // Using smart pointers for dynamic allocation (ensures no memory leaks per SE constraints)
    unique_ptr<Contract[]> L(new Contract[n1]);
    unique_ptr<Contract[]> R(new Contract[n2]);

    for (int i = 0; i < n1; i++) L[i] = arr[left + i];
    for (int j = 0; j < n2; j++) R[j] = arr[mid + 1 + j];

    int i = 0, j = 0, k = left;
    while (i < n1 && j < n2) {
        if (L[i].deadlineTimestamp <= R[j].deadlineTimestamp) {
            arr[k++] = L[i++];
        } else {
            arr[k++] = R[j++];
        }
    }

    while (i < n1) arr[k++] = L[i++];
    while (j < n2) arr[k++] = R[j++];
}

/*
 * Algorithm: Merge Sort (Divide & Conquer)
 * 
 * Time Complexity: O(N log N)
 *   where N is the number of contracts. The array is recursively divided in half and merged.
 * Space Complexity: O(N)
 *   Auxiliary space used in the merge step.
 */
void mergeSortContracts(vector<Contract>& arr, int left, int right) {
    if (left >= right) return;
    int mid = left + (right - left) / 2;
    mergeSortContracts(arr, left, mid);
    mergeSortContracts(arr, mid + 1, right);
    mergeContracts(arr, left, mid, right);
}

/*
 * Algorithm: Wrapper for sorting contracts via Merge Sort
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 */
json sortContracts(const json& contractsData) {
    vector<Contract> contracts;
    for (const auto& c : contractsData) {
        contracts.push_back({
            c["contractId"],
            c["hospitalId"],
            c["deadlineTimestamp"]
        });
    }

    if (!contracts.empty()) {
        mergeSortContracts(contracts, 0, contracts.size() - 1);
    }

    json sortedJson = json::array();
    for (const auto& c : contracts) {
        sortedJson.push_back({
            {"contractId", c.contractId},
            {"hospitalId", c.hospitalId},
            {"deadlineTimestamp", c.deadlineTimestamp}
        });
    }

    return sortedJson;
}

// ==========================================
// 5. Hash Maps (Matching Engine)
// ==========================================

/*
 * Algorithm: Hash Map matching engine for blood supply and demand
 * 
 * Time Complexity: O(R + O) -> O(N)
 *   where R is the number of requests and O is the number of offers. Insertion and lookup
 *   in an unordered_map take O(1) on average.
 * Space Complexity: O(O)
 *   for storing the offers in the unordered_map.
 */
json matchBloodRequests(const json& offersData, const json& requestsData) {
    // Map BloodType -> vector of hospital IDs offering it
    unordered_map<string, vector<string>> availableOffers;

    for (const auto& offer : offersData) {
        availableOffers[offer["bloodType"]].push_back(offer["hospitalId"]);
    }

    json matches = json::array();

    for (const auto& request : requestsData) {
        string requestedType = request["bloodType"];
        string requestingHospital = request["hospitalId"];

        if (availableOffers.find(requestedType) != availableOffers.end() && !availableOffers[requestedType].empty()) {
            string offeringHospital = availableOffers[requestedType].back();
            availableOffers[requestedType].pop_back(); // Consume the offer

            matches.push_back({
                {"requestingHospital", requestingHospital},
                {"offeringHospital", offeringHospital},
                {"bloodType", requestedType}
            });
        }
    }

    return matches;
}

// ==========================================
// 6. AI Heuristics (Donor Risk Scoring)
// ==========================================

/*
 * Algorithm: Donor Risk Scoring (AI Heuristics)
 * 
 * Time Complexity: O(R * D)
 *   where R is the number of rules and D is the number of diseases per donor.
 * Space Complexity: O(R)
 *   for the knowledge base vector of rules.
 */
json riskScoreDonor(const json& donor) {
    int score = 100;
    json penalties = json::array();

    int age = donor.value("age", 0);
    float weight_kg = donor.value("weight_kg", 0.0f);
    bool on_blood_thinners = donor.value("on_blood_thinners", false);
    int days_since_last_donation = donor.value("days_since_last_donation", 999);
    
    vector<string> diseases;
    if (donor.contains("diseases") && donor["diseases"].is_array()) {
        for (const auto& d : donor["diseases"]) {
            diseases.push_back(d.get<string>());
        }
    }
    
    int systolic_bp = donor.value("systolic_bp", 120);
    int diastolic_bp = donor.value("diastolic_bp", 80);

    vector<pair<bool, tuple<string, int, string>>> knowledgeBase = {
        { age < 18 || age > 65, {"Age", 20, "Age outside safe range"} },
        { weight_kg < 50.0f, {"Weight", 20, "Below minimum weight (50kg)"} },
        { on_blood_thinners, {"Medication", 30, "Anticoagulant medication"} },
        { days_since_last_donation < 90, {"Donation Interval", 15, "Insufficient recovery (<90 days)"} },
        { find(diseases.begin(), diseases.end(), "Diabetes") != diseases.end(), {"Condition", 10, "Chronic condition: Diabetes"} },
        { find(diseases.begin(), diseases.end(), "Hypertension") != diseases.end(), {"Condition", 10, "Chronic condition: Hypertension"} },
        { find(diseases.begin(), diseases.end(), "HepB") != diseases.end() || find(diseases.begin(), diseases.end(), "HepC") != diseases.end() || find(diseases.begin(), diseases.end(), "HIV") != diseases.end(), {"Pathogen", 100, "Transmissible pathogen — BLOCKED"} },
        { systolic_bp > 160 || diastolic_bp > 100, {"Blood Pressure", 15, "Hypertensive reading"} }
    };

    for (const auto& [condition, rule] : knowledgeBase) {
        if (condition) {
            auto [name, deduction, reason] = rule;
            score -= deduction;
            penalties.push_back({
                {"rule", name},
                {"deduction", deduction},
                {"reason", reason}
            });
        }
    }

    score = max(0, min(100, score));

    string classification = "BLOCKED";
    if (score >= 80) classification = "SAFE";
    else if (score >= 50) classification = "CAUTION";

    return {
        {"final_score", score},
        {"classification", classification},
        {"penalties", penalties},
        {"recommendation", (classification == "SAFE") ? "Eligible" : "Needs review"}
    };
}

// ==========================================
// 7. Expert System (Forward Chaining Inference Engine)
// ==========================================

/*
 * Algorithm: Rule-Based Expert System (Forward Chaining Inference Engine)
 * 
 * Time Complexity: O(R log R)
 *   where R is the number of rules, for evaluating and sorting the fired rules.
 * Space Complexity: O(R)
 *   for storing the fired rules array.
 */
json expertScreenVitals(const json& vitals) {
    struct Rule {
        string name;
        function<bool()> condition;
        string consequence;
        string action;
        int priority;
    };

    string hiv_status = vitals.value("hiv_status", "negative");
    string hepb_status = vitals.value("hepb_status", "negative");
    string hepc_status = vitals.value("hepc_status", "negative");
    string syphilis_status = vitals.value("syphilis_status", "negative");
    string malaria_status = vitals.value("malaria_status", "negative");
    float hemoglobin = vitals.value("hemoglobin", 15.0f);
    int pulse = vitals.value("pulse", 75);
    float temp_c = vitals.value("temp_c", 37.0f);

    vector<Rule> knowledgeBase = {
        {"HIV_CHECK", [&]() { return hiv_status == "positive"; }, "BLOODBORNE_PATHOGEN", "BLOCK", 10},
        {"HEPB_CHECK", [&]() { return hepb_status == "positive"; }, "BLOODBORNE_PATHOGEN", "BLOCK", 10},
        {"HEPC_CHECK", [&]() { return hepc_status == "positive"; }, "BLOODBORNE_PATHOGEN", "BLOCK", 9},
        {"SYPHILIS_CHECK", [&]() { return syphilis_status == "positive"; }, "STI_DETECTED", "BLOCK", 8},
        {"MALARIA_CHECK", [&]() { return malaria_status == "positive"; }, "PARASITIC_INFECTION", "DEFER_6_MONTHS", 7},
        {"LOW_HEMOGLOBIN", [&]() { return hemoglobin < 12.5f; }, "ANEMIA_RISK", "DEFER_PENDING_TREATMENT", 5},
        {"HIGH_PULSE", [&]() { return pulse > 100 || pulse < 50; }, "CARDIAC_ANOMALY", "CAUTION_REFER", 4},
        {"FEVER_CHECK", [&]() { return temp_c > 37.5f; }, "ACTIVE_INFECTION", "DEFER_2_WEEKS", 6}
    };

    vector<Rule> fired_rules;
    for (const auto& rule : knowledgeBase) {
        if (rule.condition()) {
            fired_rules.push_back(rule);
        }
    }

    sort(fired_rules.begin(), fired_rules.end(), [](const Rule& a, const Rule& b) {
        return a.priority > b.priority;
    });

    string verdict = "APPROVED";
    if (!fired_rules.empty()) {
        verdict = fired_rules.front().action;
    }

    json fired_rules_json = json::array();
    vector<string> inference_chain;
    for (const auto& rule : fired_rules) {
        fired_rules_json.push_back({
            {"rule", rule.name},
            {"consequence", rule.consequence},
            {"action", rule.action},
            {"priority", rule.priority}
        });
        inference_chain.push_back(rule.name);
    }

    return {
        {"verdict", verdict},
        {"fired_rules", fired_rules_json},
        {"total_rules_evaluated", (int)knowledgeBase.size()},
        {"inference_chain", inference_chain}
    };
}


// ==========================================
// Main Entry Point
// ==========================================

/*
 * Algorithm: Main IPC Handler
 * 
 * Time Complexity: Depends on the command invoked. (O(N) to parse JSON input)
 * Space Complexity: O(N) to store the parsed JSON object in memory.
 */
int main() {
    // Optimize standard I/O operations for performance
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);

    try {
        // Read all input from stdin
        string inputStr((istreambuf_iterator<char>(cin)), istreambuf_iterator<char>());
        if (inputStr.empty()) return 0;

        json request = json::parse(inputStr);
        json response;

        string command = request.value("command", "");

        if (command == "dijkstra") {
            response = findShortestPath(
                request["graph"], 
                request["startNode"], 
                request["targetNode"]
            );
        } 
        else if (command == "bfs") {
            response = findNearestBackupHospital(
                request["graph"], 
                request["inventory"], 
                request["startNode"], 
                request["requiredBloodType"]
            );
        } 
        else if (command == "min_heap") {
            response = processFEFO(request["bloodUnits"]);
        } 
        else if (command == "merge_sort") {
            response = sortContracts(request["contracts"]);
        } 
        else if (command == "hash_match") {
            response = matchBloodRequests(
                request["offers"], 
                request["requests"]
            );
        } 
        else if (command == "risk_score") {
            response = riskScoreDonor(request["donor"]);
        }
        else if (command == "expert_screen") {
            response = expertScreenVitals(request["vitals"]);
        }
        else {
            response["error"] = "Unknown command";
        }

        // Output JSON to stdout
        cout << response.dump(4) << "\n";

    } catch (const json::parse_error& e) {
        cerr << "JSON Parse Error: " << e.what() << "\n";
        return 1;
    } catch (const exception& e) {
        cerr << "Error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
