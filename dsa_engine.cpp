// BUILD: mkdir build && cd build
//        cmake .. && cmake --build .
//        Copy dsa_engine(.exe) to project root

#include <iostream>
#include <string>
#include <vector>
#include <queue>
#include <unordered_map>
#include <map>
#include <algorithm>
#include <climits>
#include "json.hpp"

using json = nlohmann::json;
using namespace std;

// ============================================================================
// 1. OPERATION: fefo_sort (Min-Heap Priority Queue)
// ============================================================================
/*
 * DSA: MIN-HEAP (Priority Queue)
 * Why: Blood units sorted by expiry. Soonest expiring = top.
 * This is FEFO: First Expire First Out.
 * Insert: O(log n) | Get minimum: O(1)
 */
struct BloodUnit {
    string id;
    string group;
    string expiry;
    json original_data;

    // We want the smallest date at the top, so we reverse the < operator for priority_queue
    bool operator>(const BloodUnit& other) const {
        return expiry > other.expiry; 
    }
};

string handle_fefo(const json& data) {
    priority_queue<BloodUnit, vector<BloodUnit>, greater<BloodUnit>> min_heap;
    
    for (auto& u : data["units"]) {
        min_heap.push({u["id"], u["blood_group"], u["expiry_date"], u});
    }
    
    json result = json::object();
    json sorted_array = json::array();
    
    while (!min_heap.empty()) {
        sorted_array.push_back(min_heap.top().original_data);
        min_heap.pop();
    }
    
    result["sorted_units"] = sorted_array;
    return result.dump();
}

// ============================================================================
// 2. OPERATION: dijkstra (Weighted Graph)
// ============================================================================
/*
 * DSA: WEIGHTED GRAPH + DIJKSTRA'S ALGORITHM
 * Graph: hospitals=nodes, roads=edges, distance=weight
 * Dijkstra finds shortest path to nearest hospital with blood.
 * Time: O((V+E) log V) using priority queue
 */
string handle_dijkstra(const json& data) {
    string source = data["source_id"];
    vector<string> available = data["available_hospitals"].get<vector<string>>();
    
    unordered_map<string, vector<pair<string, float>>> adj;
    for (auto& edge : data["edges"]) {
        string u = edge["from_id"];
        string v = edge["to_id"];
        float w = edge["distance_km"];
        adj[u].push_back({v, w});
        adj[v].push_back({u, w}); // undirected
    }

    unordered_map<string, float> dist;
    unordered_map<string, string> prev;
    for (auto& h : data["hospitals"]) dist[h["id"]] = 1e9;
    dist[source] = 0;

    priority_queue<pair<float, string>, vector<pair<float, string>>, greater<pair<float, string>>> pq;
    pq.push({0.0, source});

    while (!pq.empty()) {
        float d = pq.top().first;
        string u = pq.top().second;
        pq.pop();

        if (d > dist[u]) continue;

        for (auto& edge : adj[u]) {
            string v = edge.first;
            float weight = edge.second;
            if (dist[u] + weight < dist[v]) {
                dist[v] = dist[u] + weight;
                prev[v] = u;
                pq.push({dist[v], v});
            }
        }
    }

    // Find closest available
    float min_dist = 1e9;
    string target = "";
    for (string avail : available) {
        if (avail != source && dist[avail] < min_dist) {
            min_dist = dist[avail];
            target = avail;
        }
    }

    json result = json::object();
    if (target == "") {
        result["matched"] = false;
        return result.dump();
    }

    vector<string> path;
    string curr = target;
    while (curr != "") {
        path.push_back(curr);
        if (prev.find(curr) == prev.end()) break;
        curr = prev[curr];
    }
    reverse(path.begin(), path.end());

    result["matched"] = true;
    result["path"] = path;
    result["distance_km"] = min_dist;
    result["target_id"] = target;
    return result.dump();
}

// ============================================================================
// 3. OPERATION: bfs_backup (Breadth-First Search)
// ============================================================================
/*
 * DSA: BREADTH FIRST SEARCH
 * Explores hospital network level by level to find backup options.
 * Time: O(V+E)
 */
string handle_bfs(const json& data) {
    string source = data["source_id"];
    vector<string> available = data["available_hospitals"].get<vector<string>>();
    
    unordered_map<string, vector<string>> adj;
    for (auto& edge : data["edges"]) {
        string u = edge["from_id"];
        string v = edge["to_id"];
        adj[u].push_back(v);
        adj[v].push_back(u);
    }

    unordered_map<string, int> level;
    queue<string> q;
    q.push(source);
    level[source] = 0;

    json backups = json::array();
    
    while (!q.empty()) {
        string u = q.front();
        q.pop();

        if (u != source && find(available.begin(), available.end(), u) != available.end()) {
            json b;
            b["hospital_id"] = u;
            b["level"] = level[u];
            backups.push_back(b);
        }

        for (string v : adj[u]) {
            if (level.find(v) == level.end()) {
                level[v] = level[u] + 1;
                q.push(v);
            }
        }
    }

    json result;
    result["backups"] = backups;
    return result.dump();
}

// ============================================================================
// 4. OPERATION: find_exchange_match (Hash Map)
// ============================================================================
/*
 * DSA: HASH MAP
 * Map: needs_group -> list of offers
 * O(1) average lookup vs O(n) linear scan
 */
string handle_exchange(const json& data) {
    auto new_offer = data["new_offer"];
    string we_have = new_offer["has_group"];
    string we_need = new_offer["needs_group"];
    int units = new_offer["units"];

    unordered_map<string, vector<json>> offer_map;
    for (auto& offer : data["existing_offers"]) {
        if (offer["status"] == "pending") {
            offer_map[offer["needs_group"].get<string>()].push_back(offer);
        }
    }

    json result = json::object();
    result["matched"] = false;

    // Check if anyone needs what we have, and has what we need
    if (offer_map.find(we_have) != offer_map.end()) {
        for (auto& partner : offer_map[we_have]) {
            if (partner["has_group"] == we_need && partner["has_units"] >= units) {
                result["matched"] = true;
                result["match_id"] = partner["id"];
                result["match_hospital"] = partner["hospital_id"];
                break;
            }
        }
    }
    return result.dump();
}

// ============================================================================
// 5. OPERATION: risk_score (AI Scoring System)
// ============================================================================
/*
 * AI: RISK SCORING SYSTEM
 * Formula: score = 100 - sum(penalties)
 * Explainable AI mapping parameters to deductions.
 */
string handle_risk(const json& data) {
    int score = 100;
    json penalties = json::array();
    
    int age = data["age"];
    int days = data["days_since_donation"];
    bool thinners = data["on_blood_thinners"];
    vector<string> diseases = data["diseases"].get<vector<string>>();

    if (days < 90) { score -= 15; penalties.push_back({{"reason", "days_since_donation < 90"}, {"points", -15}}); }
    if (thinners) { score -= 30; penalties.push_back({{"reason", "On blood thinners"}, {"points", -30}}); }
    
    for (string d : diseases) {
        if (d == "Diabetes") { score -= 10; penalties.push_back({{"reason", "Diabetes"}, {"points", -10}}); }
        if (d == "Hypertension") { score -= 15; penalties.push_back({{"reason", "Hypertension"}, {"points", -15}}); }
        if (d == "HIV" || d == "HepB" || d == "HepC") { score = 0; penalties.push_back({{"reason", d}, {"points", -100}}); }
    }

    score = max(0, score);
    string level = (score >= 80) ? "safe" : ((score >= 50) ? "caution" : "blocked");

    json result;
    result["score"] = score;
    result["level"] = level;
    result["penalties"] = penalties;
    return result.dump();
}

// ============================================================================
// 6. OPERATION: screen_donor (Rule-based Expert System)
// ============================================================================
/*
 * AI: RULE-BASED EXPERT SYSTEM
 * Inference Engine: Forward Chaining
 */
struct Rule {
    string key, op, val, action;
    int priority;
    string explanation;
};

string handle_screen(const json& data) {
    vector<Rule> kb = {
        {"HIV", "contains", "HIV", "BLOCK", 10, "HIV detected"},
        {"HepB", "contains", "HepB", "BLOCK", 10, "Hepatitis B"},
        {"HepC", "contains", "HepC", "BLOCK", 10, "Hepatitis C"},
        {"age", "less_than", "18", "BLOCK", 8, "Age under 18"},
        {"days", "less_than", "90", "CAUTION", 5, "Recent donation"}
    };

    vector<string> diseases = data["diseases"].get<vector<string>>();
    int age = data["age"];
    int days = data["days_since_donation"];

    json rules_fired = json::array();
    string final_level = "safe";
    bool safe = true;
    string recommendation = "SAFE: Cleared for donation.";

    for (Rule r : kb) {
        bool fired = false;
        if (r.key == "age" && age < stoi(r.val)) fired = true;
        if (r.key == "days" && days < stoi(r.val)) fired = true;
        if (r.op == "contains" && find(diseases.begin(), diseases.end(), r.key) != diseases.end()) fired = true;

        if (fired) {
            rules_fired.push_back({{"rule", r.explanation}, {"action", r.action}, {"priority", r.priority}});
            if (r.action == "BLOCK") {
                safe = false;
                final_level = "blocked";
                recommendation = "BLOCKED: " + r.explanation;
                break; // Highest priority block stops processing
            } else if (final_level == "safe") {
                final_level = "caution";
                recommendation = "CAUTION: Review required.";
            }
        }
    }

    json result;
    result["safe"] = safe;
    result["level"] = final_level;
    result["rules_fired"] = rules_fired;
    result["recommendation"] = recommendation;
    return result.dump();
}

// ============================================================================
// 7. OPERATION: sort_contracts (Merge Sort)
// ============================================================================
/*
 * DSA: MERGE SORT
 * Sort contracts by return deadline (soonest first). Time: O(n log n)
 */
void mergeSort(vector<json>& arr, int l, int r) {
    if (l >= r) return;
    int m = l + (r - l) / 2;
    mergeSort(arr, l, m);
    mergeSort(arr, m + 1, r);

    vector<json> temp;
    int i = l, j = m + 1;
    while (i <= m && j <= r) {
        if (arr[i]["deadline_unix"] <= arr[j]["deadline_unix"]) temp.push_back(arr[i++]);
        else temp.push_back(arr[j++]);
    }
    while (i <= m) temp.push_back(arr[i++]);
    while (j <= r) temp.push_back(arr[j++]);
    for (int k = l; k <= r; k++) arr[k] = temp[k - l];
}

string handle_sort(const json& data) {
    vector<json> contracts = data["contracts"].get<vector<json>>();
    mergeSort(contracts, 0, contracts.size() - 1);
    
    json result;
    result["sorted"] = contracts;
    return result.dump();
}

// ============================================================================
// 8. OPERATION: detect_reaction (Reflex Agent)
// ============================================================================
/*
 * AI: RULE-BASED REACTION DETECTOR
 * Model-Based Reflex Agent
 */
string handle_reaction(const json& data) {
    auto pre = data["pre"];
    auto post = data["post"];

    float temp_rise = post["temp"].get<float>() - pre["temp"].get<float>();
    int bp_drop = pre["bp_sys"].get<int>() - post["bp_sys"].get<int>();
    int bp_rise = post["bp_sys"].get<int>() - pre["bp_sys"].get<int>();

    json result;
    if (post["o2"] < 90 && post["bp_sys"] < 80) {
        result = {{"reaction", "ANAPHYLAXIS"}, {"severity", 10}, {"action", "STOP. CODE BLUE."}, {"rule", "o2<90 AND bp_sys<80"}};
    } else if (temp_rise > 2.0 && bp_drop > 30) {
        result = {{"reaction", "HEMOLYTIC"}, {"severity", 9}, {"action", "STOP. Call doctor immediately."}, {"rule", "temp_rise>2.0 AND bp_drop>30"}};
    } else if (temp_rise > 1.5) {
        result = {{"reaction", "FEVER"}, {"severity", 7}, {"action", "Slow rate. Notify doctor."}, {"rule", "temp_rise>1.5"}};
    } else if (bp_rise > 20) {
        result = {{"reaction", "BP_SPIKE"}, {"severity", 6}, {"action", "Monitor closely."}, {"rule", "bp_sys_rise>20"}};
    } else {
        result = {{"reaction", "NORMAL"}, {"severity", 0}, {"action", "Continue normally ✓"}, {"rule", "none"}};
    }

    result["temp_rise"] = temp_rise;
    return result.dump();
}

// ============================================================================
// MAIN ENTRY POINT
// ============================================================================
int main() {
    string input_json;
    getline(cin, input_json);
    
    if (input_json.empty()) return 1;

    try {
        auto data = json::parse(input_json);
        string op = data["operation"];
        
        if (op == "fefo_sort")               cout << handle_fefo(data);
        else if (op == "dijkstra")           cout << handle_dijkstra(data);
        else if (op == "bfs_backup")         cout << handle_bfs(data);
        else if (op == "find_exchange_match")cout << handle_exchange(data);
        else if (op == "risk_score")         cout << handle_risk(data);
        else if (op == "screen_donor")       cout << handle_screen(data);
        else if (op == "sort_contracts")     cout << handle_sort(data);
        else if (op == "detect_reaction")    cout << handle_reaction(data);
        else cout << R"({"error": "Unknown operation"})";
    } catch (const exception& e) {
        cout << "{\"error\": \"" << e.what() << "\"}";
    }

    return 0;
}
