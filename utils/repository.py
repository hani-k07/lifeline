"""
Repository Module for LIFELINE v5.0.

Implements the Repository and Observer patterns to provide a clean, centralized,
and safe data access layer using SQLite. All queries strictly utilize parameterized
execution to prevent SQL injection vulnerabilities.
"""

import os
import uuid
import hashlib
import sqlite3
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# ==========================================
# SUBSYSTEM — CONTEXT MANAGER
# ==========================================

class DatabaseManager:
    """
    Context manager for safe SQLite connections and transactions.
    Ensures commits on success, rollbacks on errors, and guaranteed connection closures.
    """

    def __init__(self, db_path: str = "lifeline.db"):
        """
        Initializes the DatabaseManager.

        Args:
            db_path (str): The relative or absolute path to the SQLite database file.
        """
        # Support in-memory databases for testing
        if db_path == ":memory:":
            self.db_path = db_path
        elif not os.path.isabs(db_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, db_path)
        else:
            self.db_path = db_path
            
        self.conn = None

    def __enter__(self) -> 'DatabaseManager':
        """
        Enters the runtime context, establishing the database connection.

        Returns:
            DatabaseManager: The instantiated context manager.
        """
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exits the runtime context, committing or rolling back based on exception presence.
        Always closes the connection safely.
        """
        if self.conn:
            try:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
            finally:
                self.conn.close()
                self.conn = None

    def execute(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Executes a SELECT query and returns a list of dictionaries.

        Args:
            sql (str): Parameterized SQL query string.
            params (tuple): Parameters to bind to the SQL query.

        Returns:
            List[Dict[str, Any]]: The fetched rows represented as dictionaries.
        """
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def execute_write(self, sql: str, params: tuple = ()) -> Any:
        """
        Executes an INSERT, UPDATE, or DELETE query and returns the last row ID.

        Args:
            sql (str): Parameterized SQL query string.
            params (tuple): Parameters to bind to the SQL query.

        Returns:
            Any: The last inserted row ID or modified row identifier.
        """
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return cursor.lastrowid

# ==========================================
# SUBSYSTEM — OBSERVER PATTERN
# ==========================================

class AuditObserver(ABC):
    """
    Abstract interface for the Observer pattern targeting system audit logs.
    """

    @abstractmethod
    def on_event(self, action: str, entity_type: str, entity_id: str, actor_id: str, hospital_id: str, details: str) -> None:
        """
        Triggered when a watched event occurs in a repository.

        Args:
            action (str): The specific action string identifier.
            entity_type (str): The type of entity modified.
            entity_id (str): The ID of the modified entity.
            actor_id (str): The ID of the user performing the action.
            hospital_id (str): The UUID of the hospital.
            details (str): JSON or plain text details of the action.
        """
        pass

class AuditLogger(AuditObserver):
    """
    Concrete observer that writes cryptographic ledger audit logs.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initializes the AuditLogger.

        Args:
            db_manager (DatabaseManager): Connected database manager instance.
        """
        self.db = db_manager

    def on_event(self, action: str, entity_type: str, entity_id: str, actor_id: str, hospital_id: str, details: str) -> None:
        """
        Calculates cryptographic chain hashes and logs the event to the audit_logs table.
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Fetch previous hash for the specific hospital ledger chain
        sql_fetch = "SELECT current_hash FROM audit_logs WHERE hospital_id = ? ORDER BY created_at DESC LIMIT 1"
        rows = self.db.execute(sql_fetch, (hospital_id,))
        previous_hash = rows[0]['current_hash'] if rows else "0000000000000000000000000000000000000000000000000000000000000000"
        
        # Calculate new SHA-256 hash securely
        payload = f"{previous_hash}{action}{entity_id}{timestamp}".encode('utf-8')
        current_hash = hashlib.sha256(payload).hexdigest()
        
        log_id = str(uuid.uuid4())
        
        sql_insert = """
            INSERT INTO audit_logs (id, action, actor_id, hospital_id, entity_type, entity_id, details, previous_hash, current_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        self.db.execute_write(
            sql_insert,
            (log_id, action, actor_id, hospital_id, entity_type, entity_id, details, previous_hash, current_hash, timestamp)
        )

# ==========================================
# SUBSYSTEM — REPOSITORIES
# ==========================================

class BloodUnitRepository:
    """
    Repository for managing blood unit data records.
    """

    def __init__(self, db_manager: DatabaseManager, observers: Optional[List[AuditObserver]] = None):
        """
        Initializes the repository with database context and observers.

        Args:
            db_manager (DatabaseManager): Standard database connection manager.
            observers (List[AuditObserver], optional): Subscribed observers for event auditing.
        """
        self.db = db_manager
        self.observers = observers or []

    def _notify(self, action: str, entity_id: str, actor_id: str, hospital_id: str, details: str) -> None:
        """
        Notifies all attached observers of an event.
        """
        for observer in self.observers:
            observer.on_event(action, "blood_units", entity_id, actor_id, hospital_id, details)

    def add_unit(self, unit_data: Dict[str, Any], actor_id: str) -> str:
        """
        Inserts a new blood unit record.

        Args:
            unit_data (Dict[str, Any]): Dictionary containing unit attributes.
            actor_id (str): Identifier of the user performing the operation.

        Returns:
            str: The UUID of the newly inserted blood unit.
        """
        unit_id = unit_data.get('id', str(uuid.uuid4()))
        hospital_id = unit_data.get('hospital_id')
        
        sql = """
            INSERT INTO blood_units (id, hospital_id, donor_id, blood_group, component, volume_ml, collection_date, expiry_date, storage_temperature, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            unit_id,
            hospital_id,
            unit_data.get('donor_id'),
            unit_data.get('blood_group'),
            unit_data.get('component'),
            unit_data.get('volume_ml'),
            unit_data.get('collection_date'),
            unit_data.get('expiry_date'),
            unit_data.get('storage_temperature'),
            unit_data.get('status', 'available')
        )
        
        self.db.execute_write(sql, params)
        
        self._notify(
            action="BLOOD_UNIT_ADDED",
            entity_id=unit_id,
            actor_id=actor_id,
            hospital_id=hospital_id,
            details=f"Added {unit_data.get('blood_group')} blood unit."
        )
        
        return unit_id

    def get_expiring_units(self, hospital_id: str, days_threshold: int = 7) -> List[Dict[str, Any]]:
        """
        Fetches available blood units expiring within a specified timeframe.
        Pre-filters for FEFO compatibility before dispatching to C++ backend.

        Args:
            hospital_id (str): Target hospital UUID.
            days_threshold (int): Lookahead duration in days.

        Returns:
            List[Dict[str, Any]]: Sorted list of available units nearing expiration.
        """
        target_date = (datetime.utcnow() + timedelta(days=days_threshold)).strftime('%Y-%m-%d %H:%M:%S')
        
        sql = """
            SELECT id, hospital_id, donor_id, blood_group, component, volume_ml, collection_date, expiry_date, storage_temperature, status
            FROM blood_units 
            WHERE hospital_id = ? AND status = 'available' AND expiry_date <= ?
            ORDER BY expiry_date ASC
        """
        
        return self.db.execute(sql, (hospital_id, target_date))

    def get_units_by_group(self, hospital_id: str, blood_group: str) -> List[Dict[str, Any]]:
        """
        Retrieves all currently available blood units of a specified group.

        Args:
            hospital_id (str): Target hospital UUID.
            blood_group (str): Required blood group format (e.g., 'O+').

        Returns:
            List[Dict[str, Any]]: Matching blood unit records.
        """
        sql = """
            SELECT id, hospital_id, donor_id, blood_group, component, volume_ml, collection_date, expiry_date, storage_temperature, status
            FROM blood_units
            WHERE hospital_id = ? AND blood_group = ? AND status = 'available'
        """
        
        return self.db.execute(sql, (hospital_id, blood_group))

    def update_unit_status(self, unit_id: str, new_status: str, actor_id: str) -> bool:
        """
        Modifies the status lifecycle state of a given blood unit.

        Args:
            unit_id (str): Target unit UUID.
            new_status (str): The new status to apply.
            actor_id (str): Identifier of the user performing the operation.

        Raises:
            ValueError: If the provided new_status is not in the allowed lifecycle.

        Returns:
            bool: True indicating successful execution.
        """
        valid_statuses = {'available', 'reserved', 'used', 'expired'}
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: '{new_status}'. Allowed: {valid_statuses}")
            
        sql_fetch = "SELECT hospital_id FROM blood_units WHERE id = ?"
        rows = self.db.execute(sql_fetch, (unit_id,))
        if not rows:
            return False
            
        hospital_id = rows[0]['hospital_id']

        sql = "UPDATE blood_units SET status = ? WHERE id = ?"
        self.db.execute_write(sql, (new_status, unit_id))
        
        self._notify(
            action="BLOOD_UNIT_STATUS_CHANGED",
            entity_id=unit_id,
            actor_id=actor_id,
            hospital_id=hospital_id,
            details=f"Status changed to {new_status}"
        )
        return True

    def delete_unit(self, unit_id: str, actor_id: str) -> bool:
        """
        Soft-deletes a blood unit by marking it as expired instead of a hard SQL DELETE.

        Args:
            unit_id (str): Target unit UUID.
            actor_id (str): Identifier of the user performing the operation.

        Returns:
            bool: True indicating successful execution.
        """
        sql_fetch = "SELECT hospital_id FROM blood_units WHERE id = ?"
        rows = self.db.execute(sql_fetch, (unit_id,))
        if not rows:
            return False
            
        hospital_id = rows[0]['hospital_id']

        sql = "UPDATE blood_units SET status = 'expired' WHERE id = ?"
        self.db.execute_write(sql, (unit_id,))
        
        self._notify(
            action="BLOOD_UNIT_DELETED",
            entity_id=unit_id,
            actor_id=actor_id,
            hospital_id=hospital_id,
            details="Soft-deleted unit (marked expired)."
        )
        return True


class ContractRepository:
    """
    Repository for managing inter-hospital borrow contracts.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initializes the contract repository.

        Args:
            db_manager (DatabaseManager): Standard database connection manager.
        """
        self.db = db_manager

    def get_active_contracts(self, hospital_id: str) -> List[Dict[str, Any]]:
        """
        Fetches currently active contracts for a specific hospital.

        Args:
            hospital_id (str): Target hospital UUID.

        Returns:
            List[Dict[str, Any]]: Active contract records.
        """
        sql = """
            SELECT id, hospital_id, provider_id, blood_group, units_borrowed, return_deadline, status, created_at 
            FROM contracts 
            WHERE hospital_id = ? AND status = 'active'
        """
        return self.db.execute(sql, (hospital_id,))

    def get_overdue_contracts(self) -> List[Dict[str, Any]]:
        """
        Identifies active contracts that have breached their return deadlines.

        Returns:
            List[Dict[str, Any]]: Overdue contract records across the network.
        """
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        sql = """
            SELECT id, hospital_id, provider_id, blood_group, units_borrowed, return_deadline, status, created_at 
            FROM contracts 
            WHERE status = 'active' AND return_deadline < ?
        """
        return self.db.execute(sql, (now,))

    def mark_returned(self, contract_id: str, actor_id: str) -> bool:
        """
        Updates a contract lifecycle state to returned.

        Args:
            contract_id (str): Target contract UUID.
            actor_id (str): System/User completing the contract.

        Returns:
            bool: True indicating execution success.
        """
        sql = "UPDATE contracts SET status = 'returned' WHERE id = ?"
        self.db.execute_write(sql, (contract_id,))
        return True

    def get_all_for_merge_sort(self, hospital_id: str) -> List[Dict[str, Any]]:
        """
        Extracts raw active contract lists specifically structured for C++ merge_sort payload.

        Args:
            hospital_id (str): Target hospital UUID.

        Returns:
            List[Dict[str, Any]]: Raw payload ready list.
        """
        sql = """
            SELECT id as contractId, hospital_id as hospitalId, strftime('%s', return_deadline) as deadlineTimestamp 
            FROM contracts 
            WHERE hospital_id = ? AND status = 'active'
        """
        rows = self.db.execute(sql, (hospital_id,))
        
        # Guarantee casting of timestamp for C++ consumption
        results = []
        for row in rows:
            mapped_row = dict(row)
            try:
                mapped_row['deadlineTimestamp'] = int(mapped_row['deadlineTimestamp'])
            except (ValueError, TypeError):
                mapped_row['deadlineTimestamp'] = 0
            results.append(mapped_row)
            
        return results


# ==========================================
# DEMONSTRATION BLOCK
# ==========================================

if __name__ == "__main__":
    print("=== Testing Repository & Observer Patterns ===")
    
    # Use in-memory SQLite for isolated testing without corrupting lifeline.db
    with DatabaseManager(":memory:") as db:
        
        # 1. Mock the necessary schema for the demo
        db.execute_write("""
            CREATE TABLE blood_units (
                id TEXT PRIMARY KEY,
                hospital_id TEXT,
                donor_id TEXT,
                blood_group TEXT,
                component TEXT,
                volume_ml REAL,
                collection_date TEXT,
                expiry_date TEXT,
                storage_temperature REAL,
                status TEXT
            )
        """)
        
        db.execute_write("""
            CREATE TABLE audit_logs (
                id TEXT PRIMARY KEY,
                action TEXT,
                actor_id TEXT,
                hospital_id TEXT,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT,
                previous_hash TEXT,
                current_hash TEXT,
                created_at TEXT
            )
        """)
        
        # 2. Instantiate Observer and Repository
        logger_observer = AuditLogger(db)
        repo = BloodUnitRepository(db, observers=[logger_observer])
        
        # 3. Perform Business Operations
        print("\n[+] Inserting new blood unit...")
        test_hospital_id = str(uuid.uuid4())
        test_actor_id = "SYS-ADMIN-01"
        
        new_unit = {
            "hospital_id": test_hospital_id,
            "donor_id": str(uuid.uuid4()),
            "blood_group": "O-",
            "component": "Whole Blood",
            "volume_ml": 450.0,
            "collection_date": "2026-05-15 00:00:00",
            "expiry_date": "2026-06-25 00:00:00",
            "storage_temperature": 4.0,
            "status": "available"
        }
        
        unit_id = repo.add_unit(new_unit, actor_id=test_actor_id)
        print(f"    -> Added Unit ID: {unit_id}")
        
        print("\n[+] Updating blood unit status to 'reserved'...")
        repo.update_unit_status(unit_id, "reserved", actor_id=test_actor_id)
        print("    -> Update successful.")
        
        # 4. Verify Audit Logs Ledger Chain
        print("\n[+] Verifying Cryptographic Audit Ledger...")
        logs = db.execute("SELECT * FROM audit_logs ORDER BY created_at ASC")
        
        for i, log in enumerate(logs):
            print(f"\n    Log #{i+1}:")
            print(f"      Action: {log['action']}")
            print(f"      Entity ID: {log['entity_id']}")
            print(f"      Prev Hash: {log['previous_hash'][:16]}...")
            print(f"      Curr Hash: {log['current_hash'][:16]}...")
            
        assert len(logs) == 2, "Expected exactly 2 audit logs."
        assert logs[1]['previous_hash'] == logs[0]['current_hash'], "Ledger chain is broken!"
        
        print("\n=== All Subsystems Tested Successfully ===")
