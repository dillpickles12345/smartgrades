#!/usr/bin/env python3
"""
SQLite Database Manager for SmartGrades - Class-Based System
Handles teachers, classes, students, and grade tracking
"""

import sqlite3
import json
import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager

class DatabaseManager:
    """SQLite database manager for grade predictor with class system"""
    
    def __init__(self, db_path: str = 'smartgrades.db'):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like row access
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database with required tables"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Teachers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teachers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Classes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id INTEGER NOT NULL,
                    class_name TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    year TEXT,
                    semester TEXT,
                    grading_scale TEXT DEFAULT 'letter',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (teacher_id) REFERENCES teachers (id)
                )
            ''')
            
            # Students table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Class enrollments
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS class_enrollments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (class_id) REFERENCES classes (id),
                    FOREIGN KEY (student_id) REFERENCES students (id),
                    UNIQUE(class_id, student_id)
                )
            ''')
            
            # Assessments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    weight REAL NOT NULL CHECK (weight >= 0 AND weight <= 100),
                    due_date DATE,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (class_id) REFERENCES classes (id)
                )
            ''')
            
            # Student grades
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS student_grades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enrollment_id INTEGER NOT NULL,
                    assessment_id INTEGER NOT NULL,
                    score REAL CHECK (score >= 0 AND score <= 100),
                    submitted_at TIMESTAMP,
                    graded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (enrollment_id) REFERENCES class_enrollments (id),
                    FOREIGN KEY (assessment_id) REFERENCES assessments (id),
                    UNIQUE(enrollment_id, assessment_id)
                )
            ''')
            
            # Grade history for tracking changes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enrollment_id INTEGER NOT NULL,
                    predicted_grade REAL NOT NULL,
                    weighted_score REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (enrollment_id) REFERENCES class_enrollments (id)
                )
            ''')
            
            conn.commit()
    
    # ===============================
    # TEACHER MANAGEMENT
    # ===============================
    
    def add_teacher(self, name: str, email: str = None) -> int:
        """Add a new teacher"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO teachers (name, email)
                VALUES (?, ?)
            ''', (name, email))
            conn.commit()
            return cursor.lastrowid
    
    def get_teacher(self, teacher_id: int) -> Optional[Dict[str, Any]]:
        """Get teacher by ID"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM teachers WHERE id = ?', (teacher_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_teachers(self) -> List[Dict[str, Any]]:
        """Get all teachers"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM teachers ORDER BY name')
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_teacher(self, teacher_id: int) -> bool:
        """Delete a teacher and all associated data"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if teacher exists
            cursor.execute('SELECT id FROM teachers WHERE id = ?', (teacher_id,))
            if not cursor.fetchone():
                return False
            
            # Delete in order due to foreign key constraints
            # Get all classes for this teacher
            cursor.execute('SELECT id FROM classes WHERE teacher_id = ?', (teacher_id,))
            class_ids = [row['id'] for row in cursor.fetchall()]
            
            # Delete grades for all classes
            for class_id in class_ids:
                cursor.execute('''
                    DELETE FROM student_grades 
                    WHERE enrollment_id IN (
                        SELECT id FROM class_enrollments WHERE class_id = ?
                    )
                ''', (class_id,))
            
            # Delete enrollments
            cursor.execute('''
                DELETE FROM class_enrollments 
                WHERE class_id IN (SELECT id FROM classes WHERE teacher_id = ?)
            ''', (teacher_id,))
            
            # Delete assessments
            cursor.execute('DELETE FROM assessments WHERE class_id IN (SELECT id FROM classes WHERE teacher_id = ?)', (teacher_id,))
            
            # Delete classes
            cursor.execute('DELETE FROM classes WHERE teacher_id = ?', (teacher_id,))
            
            # Finally delete teacher
            cursor.execute('DELETE FROM teachers WHERE id = ?', (teacher_id,))
            
            conn.commit()
            return True
    
    # ===============================
    # CLASS MANAGEMENT
    # ===============================
    
    def add_class(self, teacher_id: int, class_name: str, subject: str, 
                  year: str = None, semester: str = None, grading_scale: str = 'letter') -> int:
        """Add a new class"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO classes (teacher_id, class_name, subject, year, semester, grading_scale)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (teacher_id, class_name, subject, year, semester, grading_scale))
            conn.commit()
            return cursor.lastrowid
    
    def get_teacher_classes(self, teacher_id: int) -> List[Dict[str, Any]]:
        """Get all classes for a teacher"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.*, COUNT(ce.id) as student_count
                FROM classes c
                LEFT JOIN class_enrollments ce ON c.id = ce.class_id
                WHERE c.teacher_id = ?
                GROUP BY c.id
                ORDER BY c.class_name
            ''', (teacher_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_class(self, class_id: int) -> Optional[Dict[str, Any]]:
        """Get class by ID with teacher info"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.*, t.name as teacher_name, t.email as teacher_email
                FROM classes c
                JOIN teachers t ON c.teacher_id = t.id
                WHERE c.id = ?
            ''', (class_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ===============================
    # STUDENT MANAGEMENT
    # ===============================
    
    def add_student(self, student_id: str, first_name: str, last_name: str, email: str = None) -> int:
        """Add a new student"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO students (student_id, first_name, last_name, email)
                VALUES (?, ?, ?, ?)
            ''', (student_id, first_name, last_name, email))
            conn.commit()
            return cursor.lastrowid
    
    def get_student_by_student_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Get student by student_id"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def enroll_student_in_class(self, class_id: int, student_id: str) -> int:
        """Enroll a student in a class"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get student internal ID
            cursor.execute('SELECT id FROM students WHERE student_id = ?', (student_id,))
            student_row = cursor.fetchone()
            if not student_row:
                raise ValueError(f"Student {student_id} not found")
            
            cursor.execute('''
                INSERT OR REPLACE INTO class_enrollments (class_id, student_id)
                VALUES (?, ?)
            ''', (class_id, student_row['id']))
            conn.commit()
            return cursor.lastrowid
    
    def delete_enrollment(self, enrollment_id: int) -> bool:
        """Delete an enrollment (remove student from class)"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if enrollment exists
            cursor.execute('SELECT id FROM class_enrollments WHERE id = ?', (enrollment_id,))
            if not cursor.fetchone():
                return False
            
            # Delete grades first
            cursor.execute('DELETE FROM student_grades WHERE enrollment_id = ?', (enrollment_id,))
            
            # Delete enrollment
            cursor.execute('DELETE FROM class_enrollments WHERE id = ?', (enrollment_id,))
            
            conn.commit()
            return True
    
    def delete_class(self, class_id: int) -> bool:
        """Delete a class and all associated data"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if class exists
            cursor.execute('SELECT id FROM classes WHERE id = ?', (class_id,))
            if not cursor.fetchone():
                return False
            
            # Delete in order due to foreign key constraints
            # Delete grades for this class
            cursor.execute('''
                DELETE FROM student_grades 
                WHERE enrollment_id IN (
                    SELECT id FROM class_enrollments WHERE class_id = ?
                )
            ''', (class_id,))
            
            # Delete enrollments
            cursor.execute('DELETE FROM class_enrollments WHERE class_id = ?', (class_id,))
            
            # Delete assessments
            cursor.execute('DELETE FROM assessments WHERE class_id = ?', (class_id,))
            
            # Finally delete class
            cursor.execute('DELETE FROM classes WHERE id = ?', (class_id,))
            
            conn.commit()
            return True
    
    def get_class_students(self, class_id: int) -> List[Dict[str, Any]]:
        """Get all students enrolled in a class"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.*, ce.id as enrollment_id
                FROM students s
                JOIN class_enrollments ce ON s.id = ce.student_id
                WHERE ce.class_id = ?
                ORDER BY s.last_name, s.first_name
            ''', (class_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ===============================
    # ASSESSMENT MANAGEMENT
    # ===============================
    
    def add_assessment(self, class_id: int, name: str, weight: float, 
                      due_date: str = None, description: str = None) -> int:
        """Add an assessment to a class"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO assessments (class_id, name, weight, due_date, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (class_id, name, weight, due_date, description))
            conn.commit()
            return cursor.lastrowid
    
    def get_class_assessments(self, class_id: int) -> List[Dict[str, Any]]:
        """Get all assessments for a class"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM assessments
                WHERE class_id = ?
                ORDER BY due_date, created_at
            ''', (class_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def update_assessment(self, assessment_id: int, **kwargs) -> bool:
        """Update an assessment"""
        if not kwargs:
            return False
        
        allowed_fields = ['name', 'weight', 'due_date', 'description']
        fields = []
        values = []
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        values.append(assessment_id)
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE assessments SET {', '.join(fields)}
                WHERE id = ?
            ''', values)
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_assessment(self, assessment_id: int) -> bool:
        """Delete an assessment and all associated grades"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if assessment exists
            cursor.execute('SELECT id FROM assessments WHERE id = ?', (assessment_id,))
            if not cursor.fetchone():
                return False
            
            # Delete grades for this assessment first
            cursor.execute('DELETE FROM student_grades WHERE assessment_id = ?', (assessment_id,))
            
            # Delete the assessment
            cursor.execute('DELETE FROM assessments WHERE id = ?', (assessment_id,))
            
            conn.commit()
            return True
    
    # ===============================
    # GRADE MANAGEMENT
    # ===============================
    
    def update_student_grade(self, enrollment_id: int, assessment_id: int, score: float) -> bool:
        """Update a student's grade for an assessment"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO student_grades (enrollment_id, assessment_id, score)
                VALUES (?, ?, ?)
            ''', (enrollment_id, assessment_id, score))
            conn.commit()
            
            # Save to grade history
            self.save_grade_history(enrollment_id)
            return True
    
    def get_student_grades(self, enrollment_id: int) -> List[Dict[str, Any]]:
        """Get all grades for a student in a class"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.id as assessment_id, a.name, a.weight, a.due_date, a.description, sg.score, sg.graded_at,
                       ce.class_id, c.class_name, c.subject
                FROM assessments a
                LEFT JOIN student_grades sg ON a.id = sg.assessment_id AND sg.enrollment_id = ?
                JOIN class_enrollments ce ON a.class_id = ce.class_id
                JOIN classes c ON ce.class_id = c.id
                WHERE ce.id = ?
                ORDER BY a.due_date, a.created_at
            ''', (enrollment_id, enrollment_id))
            return [dict(row) for row in cursor.fetchall()]
    
    def calculate_student_grade(self, enrollment_id: int) -> Dict[str, float]:
        """Calculate current grade for a student"""
        grades = self.get_student_grades(enrollment_id)
        
        total_weight = 0
        weighted_score = 0
        completed_weight = 0
        
        for grade in grades:
            if grade['weight'] is not None:
                total_weight += grade['weight']
                if grade['score'] is not None:
                    weighted_score += grade['score'] * grade['weight'] / 100
                    completed_weight += grade['weight']
        
        # Handle empty data gracefully
        predicted = (weighted_score / completed_weight * 100) if completed_weight > 0 else 0
        
        return {
            'total_weight': float(total_weight),
            'weighted_score': float(weighted_score),
            'completed_weight': float(completed_weight),
            'predicted': float(predicted),
            'remaining_weight': float(max(0, total_weight - completed_weight))
        }
    
    def save_grade_history(self, enrollment_id: int) -> int:
        """Save current grade calculation to history"""
        grade_data = self.calculate_student_grade(enrollment_id)
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO grade_history (enrollment_id, predicted_grade, weighted_score)
                VALUES (?, ?, ?)
            ''', (enrollment_id, grade_data['predicted'], grade_data['weighted_score']))
            conn.commit()
            return cursor.lastrowid
    
    # ===============================
    # DATA IMPORT/EXPORT
    # ===============================
    
    def import_students_from_csv(self, csv_content: str, class_id: int = None, import_grades: bool = False) -> Dict[str, Any]:
        """Import students from CSV content, optionally including grades"""
        try:
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            imported_count = 0
            grades_imported = 0
            errors = []
            
            # Get class assessments if importing grades
            assessments = {}
            if import_grades and class_id:
                class_assessments = self.get_class_assessments(class_id)
                # Create mapping from assessment name to assessment ID
                for assessment in class_assessments:
                    assessments[assessment['name']] = assessment['id']
            
            for row_num, row in enumerate(csv_reader, 1):
                try:
                    required_fields = ['student_id', 'first_name', 'last_name']
                    if not all(field in row and row[field].strip() for field in required_fields):
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue
                    
                    # Add student
                    student_internal_id = self.add_student(
                        student_id=row['student_id'].strip(),
                        first_name=row['first_name'].strip(),
                        last_name=row['last_name'].strip(),
                        email=row.get('email', '').strip() or None
                    )
                    
                    # Enroll in class if class_id provided
                    enrollment_id = None
                    if class_id:
                        enrollment_id = self.enroll_student_in_class(class_id, row['student_id'].strip())
                    
                    # Import grades if requested and class enrollment exists
                    if import_grades and enrollment_id and class_id:
                        for col_name, col_value in row.items():
                            # Look for assessment score columns (format: "AssessmentName_score")
                            if col_name.endswith('_score') and col_value.strip():
                                assessment_name = col_name[:-6]  # Remove "_score" suffix
                                if assessment_name in assessments:
                                    try:
                                        score = float(col_value.strip())
                                        if 0 <= score <= 100:  # Validate score range
                                            self.update_student_grade(enrollment_id, assessments[assessment_name], score)
                                            grades_imported += 1
                                        else:
                                            errors.append(f"Row {row_num}: Invalid score {score} for {assessment_name} (must be 0-100)")
                                    except ValueError:
                                        errors.append(f"Row {row_num}: Invalid score format for {assessment_name}: {col_value}")
                                else:
                                    # Assessment doesn't exist, skip but don't error
                                    pass
                    
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            result = {
                'success': True,
                'imported_count': imported_count,
                'errors': errors
            }
            
            if import_grades:
                result['grades_imported'] = grades_imported
                result['available_assessments'] = list(assessments.keys())
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'imported_count': 0,
                'errors': [str(e)]
            }
    
    def export_class_data(self, class_id: int) -> str:
        """Export class data including students and grades to CSV"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get class info
            class_info = self.get_class(class_id)
            if not class_info:
                return ""
            
            # Get students and their grades
            cursor.execute('''
                SELECT 
                    s.student_id,
                    s.first_name,
                    s.last_name,
                    s.email,
                    ce.id as enrollment_id
                FROM students s
                JOIN class_enrollments ce ON s.id = ce.student_id
                WHERE ce.class_id = ?
                ORDER BY s.last_name, s.first_name
            ''', (class_id,))
            
            students = cursor.fetchall()
            
            # Get assessments
            assessments = self.get_class_assessments(class_id)
            
            output = io.StringIO()
            fieldnames = ['student_id', 'first_name', 'last_name', 'email']
            fieldnames.extend([f"{a['name']}_score" for a in assessments])
            fieldnames.extend(['predicted_grade', 'total_weighted_score'])
            
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for student in students:
                row_data = {
                    'student_id': student['student_id'],
                    'first_name': student['first_name'],
                    'last_name': student['last_name'],
                    'email': student['email'] or ''
                }
                
                # Get student's grades
                grades = self.get_student_grades(student['enrollment_id'])
                grade_dict = {g['name']: g['score'] for g in grades}
                
                for assessment in assessments:
                    row_data[f"{assessment['name']}_score"] = grade_dict.get(assessment['name'], '')
                
                # Calculate predicted grade
                grade_calc = self.calculate_student_grade(student['enrollment_id'])
                row_data['predicted_grade'] = round(grade_calc['predicted'], 2)
                row_data['total_weighted_score'] = round(grade_calc['weighted_score'], 2)
                
                writer.writerow(row_data)
            
            return output.getvalue()
    
    # ===============================
    # CLASS ANALYTICS
    # ===============================
    
    def get_class_statistics(self, class_id: int) -> Dict[str, Any]:
        """Get comprehensive statistics for a class"""
        students = self.get_class_students(class_id)
        if not students:
            return {
                'student_count': 0,
                'mean_grade': 0.0,
                'std_deviation': 0.0,
                'highest_grade': 0.0,
                'lowest_grade': 0.0,
                'grade_distribution': {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0},
                'passing_rate': 0.0
            }
        
        grades = []
        grade_distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0}
        
        for student in students:
            grade_calc = self.calculate_student_grade(student['enrollment_id'])
            predicted = grade_calc.get('predicted', 0.0)
            # Ensure predicted is a valid number
            if predicted is None:
                predicted = 0.0
            else:
                predicted = float(predicted)
            grades.append(predicted)
            
            # Letter grade calculation
            if predicted >= 90:
                grade_distribution['A'] += 1
            elif predicted >= 80:
                grade_distribution['B'] += 1
            elif predicted >= 70:
                grade_distribution['C'] += 1
            elif predicted >= 60:
                grade_distribution['D'] += 1
            else:
                grade_distribution['E'] += 1
        
        if not grades:
            return {
                'student_count': len(students),
                'mean_grade': 0.0,
                'std_deviation': 0.0,
                'highest_grade': 0.0,
                'lowest_grade': 0.0,
                'grade_distribution': grade_distribution,
                'passing_rate': 0.0
            }
        
        mean = sum(grades) / len(grades) if grades else 0.0
        variance = sum((g - mean) ** 2 for g in grades) / len(grades) if grades else 0.0
        std_dev = variance ** 0.5
        
        return {
            'student_count': len(students),
            'mean_grade': round(float(mean), 2),
            'std_deviation': round(float(std_dev), 2),
            'highest_grade': round(float(max(grades)) if grades else 0.0, 2),
            'lowest_grade': round(float(min(grades)) if grades else 0.0, 2),
            'grade_distribution': grade_distribution,
            'passing_rate': round((sum(1 for g in grades if g >= 60) / len(grades) * 100) if grades else 0.0, 2)
        }