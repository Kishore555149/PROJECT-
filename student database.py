import sqlite3
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'students.db')
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')

def get_db_connection():
    """Establishes connection to the SQLite students database.
    Enforces foreign keys and parses rows as dictionaries.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database(force=False):
    """Initializes the database schema if the database does not exist or if forced.
    """
    if not force and os.path.exists(DB_FILE):
        return False
        
    print("Initializing student database...")
    with get_db_connection() as conn:
        with open(SCHEMA_FILE, 'r') as f:
            conn.executescript(f.read())
        conn.commit()
    print("Student database initialized successfully.")
    return True

def get_all_students(search_query=None, status_filter=None, sort_by=None):
    """Retrieves all students applying optional filters and sorting.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM students WHERE 1=1"
    params = []
    
    if search_query:
        query += " AND (name LIKE ? OR email LIKE ? OR student_uuid LIKE ? OR course LIKE ?)"
        search_pattern = f"%{search_query}%"
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
        
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
        
    valid_sorts = {
        'name_asc': 'name ASC',
        'name_desc': 'name DESC',
        'created_newest': 'created_at DESC',
        'created_oldest': 'created_at ASC',
        'status': 'status ASC',
        'uuid_asc': 'student_uuid ASC'
    }
    
    sort_sql = valid_sorts.get(sort_by, 'created_at DESC')
    query += f" ORDER BY {sort_sql}"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_student_by_id(student_id):
    """Retrieves a single student by their ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_student(name, email, course, status='Enrolled', student_uuid=None):
    """Inserts a new student.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Auto-generate a student UUID if not provided
        if not student_uuid:
            cursor.execute("SELECT COUNT(*) as count FROM students")
            count = cursor.fetchone()['count']
            student_uuid = f"STU-{1001 + count}"
            
        cursor.execute(
            """
            INSERT INTO students (student_uuid, name, email, course, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (student_uuid, name, email, course, status)
        )
        conn.commit()
        student_id = cursor.lastrowid
        
        # Log initial enrollment
        cursor.execute(
            """
            INSERT INTO academic_records (student_id, record_details, type)
            VALUES (?, ?, ?)
            """,
            (student_id, f"Student profile created. Initial enrollment into '{course}' course.", "Academic")
        )
        conn.commit()
        return student_id
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Integrity check failed: {str(e)}")
    finally:
        conn.close()

def update_student(student_id, student_uuid, name, email, course, status):
    """Updates an existing student profile.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT status, course FROM students WHERE id = ?", (student_id,))
        existing = cursor.fetchone()
        if not existing:
            raise ValueError("Student not found")
            
        old_status = existing['status']
        old_course = existing['course']
        
        cursor.execute(
            """
            UPDATE students
            SET student_uuid = ?, name = ?, email = ?, course = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (student_uuid, name, email, course, status, student_id)
        )
        
        # Log status/course changes
        if old_status != status:
            cursor.execute(
                """
                INSERT INTO academic_records (student_id, record_details, type)
                VALUES (?, ?, ?)
                """,
                (student_id, f"Academic status changed from '{old_status}' to '{status}'.", "Academic")
            )
            
        if old_course != course:
            cursor.execute(
                """
                INSERT INTO academic_records (student_id, record_details, type)
                VALUES (?, ?, ?)
                """,
                (student_id, f"Transferred major/course from '{old_course}' to '{course}'.", "Academic")
            )
            
        conn.commit()
        return True
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Integrity check failed: {str(e)}")
    finally:
        conn.close()

def delete_student(student_id):
    """Deletes a student by ID. Cascade delete clears academic records.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        if cursor.rowcount == 0:
            raise ValueError("Student not found")
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        raise ValueError(f"Database error: {str(e)}")
    finally:
        conn.close()

def get_academic_records(student_id):
    """Retrieves all academic history logs/records for a specific student.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM academic_records 
        WHERE student_id = ? 
        ORDER BY created_at DESC
        """,
        (student_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_academic_record(student_id, record_details, type_val='Academic'):
    """Adds a new academic record log entry for a student.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM students WHERE id = ?", (student_id,))
        if not cursor.fetchone():
            raise ValueError("Student not found")
            
        cursor.execute(
            """
            INSERT INTO academic_records (student_id, record_details, type)
            VALUES (?, ?, ?)
            """,
            (student_id, record_details, type_val)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Integrity check failed: {str(e)}")
    finally:
        conn.close()

def get_dashboard_stats():
    """Gathers dashboard statistics for the student management analytics.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Status Counts
    cursor.execute("SELECT status, COUNT(*) as count FROM students GROUP BY status")
    status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
    for status in ['Enrolled', 'Active', 'Suspended', 'Graduated']:
        status_counts.setdefault(status, 0)
        
    # 2. Total Count
    cursor.execute("SELECT COUNT(*) as total FROM students")
    total_students = cursor.fetchone()['total']
    
    # 3. Recent activity timeline
    cursor.execute(
        """
        SELECT ar.record_details as note, ar.type, ar.created_at, s.name as student_name, s.id as student_id
        FROM academic_records ar
        JOIN students s ON ar.student_id = s.id
        ORDER BY ar.created_at DESC
        LIMIT 5
        """
    )
    recent_activity = [dict(row) for row in cursor.fetchall()]
    
    # 4. Monthly registrations (last 6 months)
    cursor.execute(
        """
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
        FROM students
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
        """
    )
    monthly_data = [dict(row) for row in cursor.fetchall()]
    monthly_data.reverse()
    
    # 5. Course Distribution
    cursor.execute("SELECT course, COUNT(*) as count FROM students GROUP BY course")
    course_data = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        'status_counts': status_counts,
        'total_students': total_students,
        'recent_activity': recent_activity,
        'monthly_registration': monthly_data,
        'course_distribution': course_data
    }
