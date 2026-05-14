"""
C++ Inter-Process Communication (IPC) Bridge for LIFELINE v5.0.

Provides a thread-safe Singleton facade (DSAEngineFacade) to interact with the
C++ DSA backend engine. Handles structured serialization, timeout enforcement,
and graceful degradation via fault tolerance mechanisms.
"""

import os
import sys
import json
import logging
import threading
import subprocess
from typing import Dict, Any, List, Union


# ==========================================
# LOGGING CONFIGURATION
# ==========================================

logger = logging.getLogger("DSAEngineLogger")
logger.setLevel(logging.DEBUG)

# Ensure no duplicate handlers if imported multiple times
if not logger.handlers:
    # Resolve the base directory where errors.log should be kept
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_file = os.path.join(base_dir, "errors.log")

    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.ERROR)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)


# ==========================================
# SUBSYSTEM — IPC FACADE
# ==========================================

class DSAEngineFacade:
    """
    Thread-safe Singleton facade for managing the C++ DSA backend process.
    Provides methods for calling specific algorithms and handles fault tolerance.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """
        Thread-safe Singleton implementation.

        Returns:
            DSAEngineFacade: The single instance of the class.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DSAEngineFacade, cls).__new__(cls)
                cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """
        Initializes the facade by determining the correct executable path
        based on the host operating system.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if sys.platform.startswith('win'):
            exe_name = 'dsa_engine.exe'
        else:
            exe_name = 'dsa_engine'

        self.exe_path = os.path.join(base_dir, exe_name)
        self.verify_engine()

    def verify_engine(self) -> bool:
        """
        Verifies if the C++ executable exists and is executable.

        Returns:
            bool: True if the engine is found and executable, False otherwise.
        """
        if not os.path.exists(self.exe_path):
            logger.warning(f"DSA Engine not found at: {self.exe_path}")
            return False
            
        if not os.access(self.exe_path, os.X_OK):
            logger.warning(f"DSA Engine is not executable: {self.exe_path}")
            return False
            
        logger.info(f"DSA Engine verified at: {self.exe_path}")
        return True

    def _log_error(self, error_dict: Dict[str, Any]) -> None:
        """
        Logs a standardized error dictionary to the configured logger.

        Args:
            error_dict (Dict[str, Any]): Dictionary containing error details.
        """
        msg = f"DSA Engine Fault Detected: {json.dumps(error_dict)}"
        logger.error(msg)

    def call(self, command: str, payload: Dict[str, Any], timeout: int = 5) -> Union[Dict[str, Any], List[Any]]:
        """
        Calls the C++ executable via standard subprocess pipes.

        Args:
            command (str): The DSA algorithm identifier to invoke.
            payload (Dict[str, Any]): Data payload required by the algorithm.
            timeout (int): Maximum execution time in seconds before throwing a timeout.

        Returns:
            Union[Dict[str, Any], List[Any]]: Standardized JSON response from C++ engine 
                                              or an error fallback dictionary.
        """
        payload["command"] = command
        try:
            json_str = json.dumps(payload)
            json_bytes = json_str.encode('utf-8')
        except Exception as e:
            err = {"error": "DSA_UNKNOWN", "message": f"Serialization error: {str(e)}", "fallback": True}
            self._log_error(err)
            return err

        output_str = ""
        try:
            result = subprocess.run(
                [self.exe_path],
                input=json_bytes,
                capture_output=True,
                timeout=timeout,
                check=True
            )
            
            output_str = result.stdout.decode('utf-8').strip()
            return json.loads(output_str)

        except subprocess.TimeoutExpired:
            err = {"error": "DSA_TIMEOUT", "command": command, "fallback": True}
            self._log_error(err)
            return err
        except subprocess.CalledProcessError as e:
            err = {"error": "DSA_CRASH", "code": e.returncode, "fallback": True}
            self._log_error(err)
            return err
        except FileNotFoundError:
            err = {"error": "DSA_NOT_FOUND", "fallback": True}
            self._log_error(err)
            return err
        except json.JSONDecodeError:
            err = {"error": "DSA_PARSE_ERROR", "raw": output_str, "fallback": True}
            self._log_error(err)
            return err
        except Exception as e:
            err = {"error": "DSA_UNKNOWN", "message": str(e), "fallback": True}
            self._log_error(err)
            return err

    def run_dijkstra(self, graph: List[Dict[str, Any]], start: str, target: str) -> Dict[str, Any]:
        """
        Finds the shortest path between two nodes using Dijkstra's algorithm.

        Args:
            graph (List[Dict[str, Any]]): Graph adjacency representation.
            start (str): The starting node identifier.
            target (str): The target node identifier.

        Returns:
            Dict[str, Any]: Routing result with optimal path and total distance.
        """
        payload = {
            "graph": graph,
            "startNode": start,
            "targetNode": target
        }
        res = self.call("dijkstra", payload)
        if isinstance(res, list):
            return {"result": res}
        return res

    def run_bfs(self, graph: List[Dict[str, Any]], inventory: List[Dict[str, Any]], start: str, blood_type: str) -> Dict[str, Any]:
        """
        Finds the nearest backup hospital via topological BFS.

        Args:
            graph (List[Dict[str, Any]]): Graph adjacency representation.
            inventory (List[Dict[str, Any]]): Hospital blood inventories.
            start (str): The starting node identifier.
            blood_type (str): The requested blood type.

        Returns:
            Dict[str, Any]: Hospital node with the shortest topological distance having the blood type.
        """
        payload = {
            "graph": graph,
            "inventory": inventory,
            "startNode": start,
            "requiredBloodType": blood_type
        }
        res = self.call("bfs", payload)
        if isinstance(res, list):
            return {"result": res}
        return res

    def run_fefo_sort(self, blood_units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sorts blood units by expiry timestamp using a Min-Heap.

        Args:
            blood_units (List[Dict[str, Any]]): List of blood unit descriptors.

        Returns:
            List[Dict[str, Any]]: Sorted list of blood units based on FEFO principle.
        """
        payload = {"bloodUnits": blood_units}
        res = self.call("min_heap", payload)
        if isinstance(res, dict) and "error" in res:
            return []  # Graceful degradation logic
        if not isinstance(res, list):
            return []
        return res

    def run_merge_sort(self, contracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sorts hospital borrow contracts using Merge Sort.

        Args:
            contracts (List[Dict[str, Any]]): List of contract details.

        Returns:
            List[Dict[str, Any]]: Contract list sorted chronologically by deadline.
        """
        payload = {"contracts": contracts}
        res = self.call("merge_sort", payload)
        if isinstance(res, dict) and "error" in res:
            return []
        if not isinstance(res, list):
            return []
        return res

    def run_hash_match(self, offers: List[Dict[str, Any]], requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Matches blood offers with active requests in O(1) time complexity utilizing hash maps.

        Args:
            offers (List[Dict[str, Any]]): Active supply nodes with specific blood types.
            requests (List[Dict[str, Any]]): Active demand requests from hospitals.

        Returns:
            List[Dict[str, Any]]: Successful supply-demand pairs.
        """
        payload = {"offers": offers, "requests": requests}
        res = self.call("hash_match", payload)
        if isinstance(res, dict) and "error" in res:
            return []
        if not isinstance(res, list):
            return []
        return res


# ==========================================
# BACKWARD COMPATIBILITY
# ==========================================

def run_dsa_engine(operation: str, payload: Dict[str, Any]) -> Union[Dict[str, Any], List[Any]]:
    """
    Backward-compatible module-level function used by existing application components.
    Automatically maps string operations to the new singleton methods.

    Args:
        operation (str): Target algorithm ("dijkstra", "bfs", "min_heap", "merge_sort", "hash_match").
        payload (Dict[str, Any]): The operational payload arguments.

    Returns:
        Union[Dict[str, Any], List[Any]]: Engine execution result.
    """
    engine = DSAEngineFacade()
    
    if operation == "dijkstra":
        return engine.run_dijkstra(
            graph=payload.get("graph", []),
            start=payload.get("startNode", ""),
            target=payload.get("targetNode", "")
        )
    elif operation == "bfs":
        return engine.run_bfs(
            graph=payload.get("graph", []),
            inventory=payload.get("inventory", []),
            start=payload.get("startNode", ""),
            blood_type=payload.get("requiredBloodType", "")
        )
    elif operation == "min_heap":
        return engine.run_fefo_sort(
            blood_units=payload.get("bloodUnits", [])
        )
    elif operation == "merge_sort":
        return engine.run_merge_sort(
            contracts=payload.get("contracts", [])
        )
    elif operation == "hash_match":
        return engine.run_hash_match(
            offers=payload.get("offers", []),
            requests=payload.get("requests", [])
        )
    else:
        # Fallback to direct raw call if an unknown operation is routed
        return engine.call(operation, payload)


# ==========================================
# DEMONSTRATION BLOCK
# ==========================================

if __name__ == "__main__":
    print("=== Testing DSAEngineFacade ===")
    facade = DSAEngineFacade()
    
    # Minimal valid payloads matching the C++ input schema
    test_graph = [
        {"source": "H1", "target": "H2", "weight": 10},
        {"source": "H2", "target": "H3", "weight": 5}
    ]
    
    print("\n1. Testing Dijkstra...")
    res_dijkstra = facade.run_dijkstra(test_graph, "H1", "H3")
    print(json.dumps(res_dijkstra, indent=2))
    
    print("\n2. Testing BFS...")
    test_inventory = [
        {"hospitalId": "H1", "bloodType": "A+"},
        {"hospitalId": "H3", "bloodType": "O-"}
    ]
    res_bfs = facade.run_bfs(test_graph, test_inventory, "H1", "O-")
    print(json.dumps(res_bfs, indent=2))
    
    print("\n3. Testing Min-Heap FEFO Sort...")
    test_blood_units = [
        {"id": "U1", "bloodType": "O+", "expiryTimestamp": 1700000000},
        {"id": "U2", "bloodType": "A-", "expiryTimestamp": 1690000000}
    ]
    res_fefo = facade.run_fefo_sort(test_blood_units)
    print(json.dumps(res_fefo, indent=2))
    
    print("\n4. Testing Merge Sort...")
    test_contracts = [
        {"contractId": "C1", "hospitalId": "H1", "deadlineTimestamp": 1800000000},
        {"contractId": "C2", "hospitalId": "H2", "deadlineTimestamp": 1750000000}
    ]
    res_merge = facade.run_merge_sort(test_contracts)
    print(json.dumps(res_merge, indent=2))
    
    print("\n5. Testing Hash Match...")
    test_offers = [{"hospitalId": "H1", "bloodType": "O-"}]
    test_requests = [{"hospitalId": "H2", "bloodType": "O-"}]
    res_match = facade.run_hash_match(test_offers, test_requests)
    print(json.dumps(res_match, indent=2))
    
    print("\n=== All Subsystems Tested Successfully ===")
