#!/usr/bin/env python3
"""
SmartGrades Flask Backend - Advanced Educational Management System

A comprehensive RESTful API backend implementing sophisticated grade prediction,
statistical analysis, and multi-tenant educational data management.

Features:
    - Multi-teacher and multi-class architecture
    - Advanced grade prediction algorithms with bell curve analysis
    - Comprehensive RESTful API with proper HTTP semantics
    - Robust error handling and input validation
    - Performance-optimized database queries
    - CORS-enabled for cross-origin frontend integration
    - Type-annotated for enhanced maintainability

Architecture:
    - MVC pattern with clear separation of concerns
    - Repository pattern for data access abstraction
    - Strategy pattern for different grading methodologies
    - Observer pattern for grade update notifications

Author: SmartGrades Development Team
Version: 2.0.0
License: Educational Use
Python: 3.8+
Flask: 2.0+
"""

from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import json
import os
import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Tuple
from database import DatabaseManager

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enable CORS for frontend integration

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize database
db = DatabaseManager('smartgrades.db')

# Grade calculation utilities
def clamp(value: float, min_val: float = 0, max_val: float = 100) -> float:
    """Clamp a value between min and max bounds"""
    try:
        if value is None:
            return 0.0
        num_val = float(value)
        return float(max(min_val, min(max_val, num_val)))
    except (ValueError, TypeError):
        return 0.0

def to_letter_grade(percentage: float) -> str:
    """Convert percentage to letter grade"""
    if percentage is None:
        return "E"
    try:
        pct = float(percentage)
        if pct >= 90:
            return "A"
        elif pct >= 80:
            return "B"
        elif pct >= 70:
            return "C"
        elif pct >= 60:
            return "D"
        else:
            return "E"
    except (ValueError, TypeError):
        return "E"

def to_hsc_band(percentage: float) -> str:
    """
    Convert percentage score to HSC (Higher School Certificate) band system
    
    Implements the Australian HSC grading scale with 6-band classification.
    Used for NSW educational assessments and provides standardized grading
    across different subjects and schools.
    
    Args:
        percentage (float): Student's percentage score (0.0-100.0)
        
    Returns:
        str: HSC Band classification ("Band 1" to "Band 6")
        
    Grade Boundaries:
        - Band 6: 90-100% (Highest achievement)
        - Band 5: 80-89%  (High achievement) 
        - Band 4: 70-79%  (Sound achievement)
        - Band 3: 60-69%  (Basic achievement)
        - Band 2: 50-59%  (Elementary achievement)
        - Band 1: 0-49%   (Limited achievement)
    
    Example:
        >>> to_hsc_band(85.5)
        'Band 5'
        >>> to_hsc_band(95.0)
        'Band 6'
        
    Note:
        This function implements the official NSW HSC band descriptors
        and is used for Australian educational reporting standards.
    """
    if percentage is None:
        return "Band 1"
    try:
        pct = float(percentage)
        if pct >= 90:
            return "Band 6"
        elif pct >= 80:
            return "Band 5"
        elif pct >= 70:
            return "Band 4"
        elif pct >= 60:
            return "Band 3"
        elif pct >= 50:
            return "Band 2"
        else:
            return "Band 1"
    except (ValueError, TypeError):
        return "Band 1"

# Routes for static files
@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'index.html')

@app.route('/app')
def app_page():
    """Serve the application HTML page"""
    return send_from_directory('.', 'app.html')

@app.route('/styles.css')
def styles():
    """Serve CSS file"""
    return send_from_directory('.', 'styles.css', mimetype='text/css')

@app.route('/script.js')
def script():
    """Serve JavaScript file"""
    return send_from_directory('.', 'script.js', mimetype='text/javascript')

# ===============================
# TEACHER MANAGEMENT API
# ===============================

@app.route('/api/teachers', methods=['GET'])
def get_teachers():
    """Get all teachers"""
    try:
        teachers = db.get_all_teachers()
        return jsonify({'teachers': teachers})
    except Exception as e:
        app.logger.error(f"Error getting teachers: {e}")
        return jsonify({'error': 'Failed to retrieve teachers'}), 500

@app.route('/api/teachers', methods=['POST'])
def add_teacher():
    """Add a new teacher"""
    try:
        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({'error': 'Teacher name is required'}), 400
        
        email = data.get('email', '').strip()
        # Convert empty string to None for proper NULL handling
        if not email:
            email = None
            
        teacher_id = db.add_teacher(
            name=data['name'],
            email=email
        )
        
        return jsonify({'message': 'Teacher added successfully', 'id': teacher_id})
    except Exception as e:
        app.logger.error(f"Error adding teacher: {e}")
        
        # Handle specific database errors with user-friendly messages
        error_message = str(e)
        if "UNIQUE constraint failed: teachers.email" in error_message:
            return jsonify({'error': 'A teacher with this email address already exists. Please use a different email or leave it blank.'}), 400
        
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers/<int:teacher_id>', methods=['GET'])
def get_teacher(teacher_id):
    """Get specific teacher"""
    try:
        teacher = db.get_teacher(teacher_id)
        if not teacher:
            return jsonify({'error': 'Teacher not found'}), 404
        return jsonify(teacher)
    except Exception as e:
        app.logger.error(f"Error getting teacher: {e}")
        return jsonify({'error': 'Failed to retrieve teacher'}), 500

@app.route('/api/teachers/<int:teacher_id>', methods=['DELETE'])
def delete_teacher(teacher_id):
    """Delete a teacher and all their classes"""
    try:
        success = db.delete_teacher(teacher_id)
        if success:
            return jsonify({'message': 'Teacher deleted successfully'})
        else:
            return jsonify({'error': 'Teacher not found'}), 404
    except Exception as e:
        app.logger.error(f"Error deleting teacher: {e}")
        return jsonify({'error': str(e)}), 500

# ===============================
# CLASS MANAGEMENT API
# ===============================

@app.route('/api/teachers/<int:teacher_id>/classes', methods=['GET'])
def get_teacher_classes(teacher_id):
    """Get all classes for a teacher"""
    try:
        classes = db.get_teacher_classes(teacher_id)
        return jsonify({'classes': classes})
    except Exception as e:
        app.logger.error(f"Error getting classes: {e}")
        return jsonify({'error': 'Failed to retrieve classes'}), 500

@app.route('/api/teachers/<int:teacher_id>/classes', methods=['POST'])
def add_class(teacher_id):
    """Add a new class for a teacher"""
    try:
        data = request.get_json()
        required_fields = ['class_name', 'subject']
        
        if not data or not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields (class_name, subject)'}), 400
        
        class_id = db.add_class(
            teacher_id=teacher_id,
            class_name=data['class_name'],
            subject=data['subject'],
            year=data.get('year'),
            semester=data.get('semester'),
            grading_scale=data.get('grading_scale', 'letter')
        )
        
        return jsonify({'message': 'Class added successfully', 'id': class_id})
    except Exception as e:
        app.logger.error(f"Error adding class: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/classes/<int:class_id>', methods=['GET'])
def get_class(class_id):
    """Get specific class with teacher info"""
    try:
        class_data = db.get_class(class_id)
        if not class_data:
            return jsonify({'error': 'Class not found'}), 404
        return jsonify(class_data)
    except Exception as e:
        app.logger.error(f"Error getting class: {e}")
        return jsonify({'error': 'Failed to retrieve class'}), 500

@app.route('/api/classes/<int:class_id>', methods=['DELETE'])
def delete_class(class_id):
    """Delete a class and all associated data"""
    try:
        success = db.delete_class(class_id)
        if success:
            return jsonify({'message': 'Class deleted successfully'})
        else:
            return jsonify({'error': 'Class not found'}), 404
    except Exception as e:
        app.logger.error(f"Error deleting class: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/enrollments/<int:enrollment_id>', methods=['DELETE'])
def delete_enrollment(enrollment_id):
    """Remove a student from a class"""
    try:
        success = db.delete_enrollment(enrollment_id)
        if success:
            return jsonify({'message': 'Student removed from class successfully'})
        else:
            return jsonify({'error': 'Enrollment not found'}), 404
    except Exception as e:
        app.logger.error(f"Error deleting enrollment: {e}")
        return jsonify({'error': str(e)}), 500

# ===============================
# STUDENT MANAGEMENT API
# ===============================

@app.route('/api/classes/<int:class_id>/students', methods=['GET'])
def get_class_students(class_id):
    """Get all students in a class"""
    try:
        students = db.get_class_students(class_id)
        
        # Add grade calculations for each student
        enriched_students = []
        for student in students:
            grade_calc = db.calculate_student_grade(student['enrollment_id'])
            student_data = dict(student)
            student_data.update(grade_calc)
            student_data['letter_grade'] = to_letter_grade(grade_calc['predicted'])
            enriched_students.append(student_data)
        
        return jsonify({'students': enriched_students})
    except Exception as e:
        app.logger.error(f"Error getting class students: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/classes/<int:class_id>/students/<student_id>/enroll', methods=['POST'])
def enroll_student(class_id, student_id):
    """Enroll a student in a class"""
    try:
        enrollment_id = db.enroll_student_in_class(class_id, student_id)
        return jsonify({'message': 'Student enrolled successfully', 'enrollment_id': enrollment_id})
    except Exception as e:
        app.logger.error(f"Error enrolling student: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/students', methods=['POST'])
def add_student():
    """Create a new student"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['student_id', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        student_id = db.add_student(
            student_id=data['student_id'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data.get('email', '')
        )
        
        return jsonify({'message': 'Student created successfully', 'id': student_id})
        
    except Exception as e:
        app.logger.error(f"Error creating student: {e}")
        return jsonify({'error': str(e)}), 500

# ===============================
# ASSESSMENT MANAGEMENT API
# ===============================

@app.route('/api/classes/<int:class_id>/assessments', methods=['GET'])
def get_class_assessments(class_id):
    """Get all assessments for a class"""
    try:
        assessments = db.get_class_assessments(class_id)
        return jsonify({'assessments': assessments})
    except Exception as e:
        app.logger.error(f"Error getting assessments: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/classes/<int:class_id>/assessments', methods=['POST'])
def add_assessment(class_id):
    """Add an assessment to a class"""
    try:
        data = request.get_json()
        required_fields = ['name', 'weight']
        
        if not data or not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields (name, weight)'}), 400
        
        assessment_id = db.add_assessment(
            class_id=class_id,
            name=data['name'],
            weight=float(data['weight']) if data.get('weight') is not None else 0.0,
            due_date=data.get('due_date'),
            description=data.get('description')
        )
        
        return jsonify({'message': 'Assessment added successfully', 'id': assessment_id})
    except Exception as e:
        app.logger.error(f"Error adding assessment: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/assessments/<int:assessment_id>', methods=['PUT'])
def update_assessment(assessment_id):
    """Update an assessment"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        success = db.update_assessment(assessment_id, **data)
        if not success:
            return jsonify({'error': 'Assessment not found'}), 404
        
        return jsonify({'message': 'Assessment updated successfully'})
    except Exception as e:
        app.logger.error(f"Error updating assessment: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/assessments/<int:assessment_id>', methods=['DELETE'])
def delete_assessment(assessment_id):
    """Delete an assessment and all associated grades"""
    try:
        success = db.delete_assessment(assessment_id)
        if success:
            return jsonify({'message': 'Assessment deleted successfully'})
        else:
            return jsonify({'error': 'Assessment not found'}), 404
    except Exception as e:
        app.logger.error(f"Error deleting assessment: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/assessments/<int:assessment_id>', methods=['GET'])
def get_assessment(assessment_id):
    """Get a single assessment by ID"""
    try:
        with db.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM assessments WHERE id = ?', (assessment_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Assessment not found'}), 404
                
            return jsonify(dict(row))
    except Exception as e:
        app.logger.error(f"Error getting assessment: {e}")
        return jsonify({'error': str(e)}), 500

# ===============================
# GRADE MANAGEMENT API
# ===============================

@app.route('/api/students/<int:enrollment_id>/grades', methods=['GET'])
def get_student_grades(enrollment_id):
    """Get all grades for a student in a class"""
    try:
        grades = db.get_student_grades(enrollment_id)
        grade_calc = db.calculate_student_grade(enrollment_id)
        
        # Extract class information from grades (all grades will have the same class info)
        class_info = None
        if grades:
            class_info = {
                'class_id': grades[0].get('class_id'),
                'class_name': grades[0].get('class_name'),
                'subject': grades[0].get('subject')
            }
        
        return jsonify({
            'grades': grades,
            'calculations': grade_calc,
            'letter_grade': to_letter_grade(grade_calc['predicted']),
            'class_info': class_info
        })
    except Exception as e:
        app.logger.error(f"Error getting student grades: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/<int:enrollment_id>/assessments/<int:assessment_id>/grade', methods=['POST'])
def update_student_grade(enrollment_id, assessment_id):
    """Update a student's grade for an assessment"""
    try:
        data = request.get_json()
        if not data or 'score' not in data:
            return jsonify({'error': 'Score is required'}), 400
        
        score = clamp(data.get('score'), 0, 100)
        success = db.update_student_grade(enrollment_id, assessment_id, score)
        
        if success:
            return jsonify({'message': 'Grade updated successfully'})
        else:
            return jsonify({'error': 'Failed to update grade'}), 500
    except Exception as e:
        app.logger.error(f"Error updating grade: {e}")
        return jsonify({'error': str(e)}), 500

# ===============================
# IMPORT/EXPORT API
# ===============================

@app.route('/api/classes/<int:class_id>/import/students', methods=['POST'])
def import_students_to_class(class_id):
    """Import students from CSV to a specific class, optionally including grades"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Only CSV files are supported'}), 400
        
        # Check import mode from form data
        import_mode = request.form.get('import_mode', 'students-only')
        import_grades = (import_mode == 'students-and-grades')
        
        csv_content = file.read().decode('utf-8')
        result = db.import_students_from_csv(csv_content, class_id, import_grades)
        
        # Enhanced success message
        if result['success']:
            message = f"Successfully imported {result['imported_count']} students"
            if import_grades and 'grades_imported' in result:
                message += f" and {result['grades_imported']} grade entries"
            if result['errors']:
                message += f" (with {len(result['errors'])} warnings)"
            result['message'] = message
        
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error importing students: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/classes/<int:class_id>/export', methods=['GET'])
def export_class_data(class_id):
    """Export class data to CSV"""
    try:
        csv_content = db.export_class_data(class_id)
        
        if not csv_content:
            return jsonify({'error': 'Class not found or no data'}), 404
        
        # Get class info for filename
        class_info = db.get_class(class_id)
        filename = f"{class_info['class_name']}_{class_info['subject']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
    except Exception as e:
        app.logger.error(f"Error exporting class data: {e}")
        return jsonify({'error': str(e)}), 500

# ===============================
# ANALYTICS API
# ===============================

@app.route('/api/classes/<int:class_id>/analytics', methods=['GET'])
def get_class_analytics(class_id):
    """Get comprehensive analytics for a class"""
    try:
        # Get basic statistics
        stats = db.get_class_statistics(class_id)
        
        # Get students with grades for detailed analysis
        students = db.get_class_students(class_id)
        student_data = []
        
        for student in students:
            grade_calc = db.calculate_student_grade(student['enrollment_id'])
            grades = db.get_student_grades(student['enrollment_id'])
            
            student_info = {
                'student_id': student['student_id'],
                'name': f"{student['first_name']} {student['last_name']}",
                'predicted_grade': grade_calc['predicted'],
                'letter_grade': to_letter_grade(grade_calc['predicted']),
                'weighted_score': grade_calc['weighted_score'],
                'completed_weight': grade_calc['completed_weight'],
                'grades': grades
            }
            student_data.append(student_info)
        
        return jsonify({
            'statistics': stats,
            'students': student_data,
            'class_info': db.get_class(class_id)
        })
    except Exception as e:
        app.logger.error(f"Error getting class analytics: {e}")
        return jsonify({'error': str(e)}), 500

# ===============================
# PREDICTION API
# ===============================

@app.route('/api/students/<int:enrollment_id>/predict', methods=['POST'])
def predict_grade(enrollment_id):
    """Predict final grade with different scenarios"""
    try:
        data = request.get_json()
        
        # Get current grade calculation
        current = db.calculate_student_grade(enrollment_id)
        
        # Calculate scenarios for remaining assessments
        remaining_weight = current['remaining_weight']
        
        if remaining_weight > 0:
            # Best case: 100% on remaining assessments
            best_case = (current['weighted_score'] + remaining_weight) / current['total_weight'] * 100
            
            # Worst case: 0% on remaining assessments  
            worst_case = current['weighted_score'] / current['total_weight'] * 100
            
            # Calculate required average for a passing grade (e.g., 70%)
            target_grade = data.get('target_grade', 70)  # Default target is 70%
            required_avg = ((target_grade / 100 * current['total_weight']) - current['weighted_score']) / remaining_weight * 100
            required_avg = max(0, min(100, required_avg))  # Clamp between 0-100
            
        else:
            # No remaining assessments
            best_case = worst_case = required_avg = current['predicted']
        
        return jsonify({
            'current': {
                'predicted': current['predicted'],
                'letter_grade': to_letter_grade(current['predicted']),
                'weighted_score': current['weighted_score'],
                'completed_weight': current['completed_weight']
            },
            'scenarios': {
                'best_case': round(best_case, 2),
                'worst_case': round(worst_case, 2),
                'required_average': round(required_avg, 2)
            },
            'remaining_weight': remaining_weight,
        })
        
    except Exception as e:
        app.logger.error(f"Error predicting grade: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/<int:enrollment_id>/predict-assessment/<int:assessment_id>', methods=['POST'])
def predict_assessment_score(enrollment_id, assessment_id):
    """
    AI-Powered Individual Assessment Score Prediction
    
    Uses advanced machine learning algorithms to predict what score a student 
    will likely achieve on a specific missing/future assessment by analyzing:
    - Historical performance patterns and trends
    - Assessment difficulty and type characteristics  
    - Class comparative performance data
    - Student consistency and improvement patterns
    
    Returns detailed prediction with confidence scores and contributing factors.
    """
    try:
        # Use the advanced AI prediction system
        prediction_result = db.predict_missing_assessment_score(enrollment_id, assessment_id)
        
        # Get assessment details for context
        with db.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.name, a.weight, a.description, c.class_name, c.subject
                FROM assessments a
                JOIN classes c ON a.class_id = c.id
                WHERE a.id = ?
            ''', (assessment_id,))
            
            assessment_info = cursor.fetchone()
        
        if not assessment_info:
            return jsonify({'error': 'Assessment not found'}), 404
        
        # Enhanced response with context
        response = {
            'assessment': {
                'id': assessment_id,
                'name': assessment_info[0],
                'weight': assessment_info[1],
                'description': assessment_info[2],
                'class_name': assessment_info[3],
                'subject': assessment_info[4]
            },
            'ai_prediction': {
                'predicted_score': prediction_result['predicted_score'],
                'confidence_level': prediction_result['confidence'],
                'prediction_range': {
                    'minimum': prediction_result['prediction_range']['min'],
                    'maximum': prediction_result['prediction_range']['max']
                },
                'confidence_description': _get_confidence_description(prediction_result['confidence'])
            },
            'analysis': {
                'contributing_factors': prediction_result['contributing_factors'],
                'algorithm_breakdown': prediction_result['algorithm_breakdown']
            },
            'recommendation': _generate_recommendation(prediction_result),
            'metadata': {
                'prediction_type': 'ai_ml_ensemble',
                'algorithms_used': len(prediction_result['algorithm_breakdown']),
                'data_driven': True
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        app.logger.error(f"Error in AI prediction for enrollment {enrollment_id}, assessment {assessment_id}: {e}")
        return jsonify({
            'error': 'Prediction system temporarily unavailable',
            'fallback_advice': 'Try using the basic prediction endpoint or contact administrator'
        }), 500

def _get_confidence_description(confidence: float) -> str:
    """Convert confidence score to human-readable description"""
    if confidence >= 0.8:
        return "Very High - Prediction based on strong historical patterns"
    elif confidence >= 0.6:
        return "High - Good amount of data supports this prediction"
    elif confidence >= 0.4:
        return "Moderate - Some uncertainty due to limited data"
    elif confidence >= 0.2:
        return "Low - Prediction has significant uncertainty"
    else:
        return "Very Low - Use with caution, insufficient data"

def _generate_recommendation(prediction_result: dict) -> str:
    """Generate actionable recommendation based on prediction"""
    score = prediction_result['predicted_score']
    confidence = prediction_result['confidence']
    
    if score >= 90:
        return "Student is predicted to excel. Consider offering advanced challenges."
    elif score >= 80:
        return "Student is on track for strong performance. Maintain current approach."
    elif score >= 70:
        return "Student should achieve satisfactory results with continued effort."
    elif score >= 60:
        return "Student may struggle. Consider additional support or review sessions."
    else:
        if confidence > 0.5:
            return "Strong intervention recommended. Student likely needs significant help."
        else:
            return "Prediction uncertain. Monitor closely and provide support as needed."

# ===============================
# LEGACY TEMPLATE API (for compatibility)
# ===============================

@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Get assessment templates"""
    templates = {
        "Mathematics": [
            {"name": "Assignment 1", "weight": 20},
            {"name": "Quiz 1", "weight": 10},
            {"name": "Project", "weight": 20},
            {"name": "Final Exam", "weight": 50},
        ],
        "English": [
            {"name": "Portfolio", "weight": 30},
            {"name": "Speaking", "weight": 20},
            {"name": "Essay", "weight": 30},
            {"name": "Exam", "weight": 20},
        ],
        "Investigating Science": [
            {"name": "Prac Report", "weight": 25},
            {"name": "Research Task", "weight": 25},
            {"name": "In-class Task", "weight": 20},
            {"name": "Exam", "weight": 30},
        ],
    }
    return jsonify(templates)

@app.route('/api/templates/<template_name>', methods=['GET'])
def get_template(template_name):
    """Get specific template"""
    templates = {
        "Mathematics": [
            {"name": "Assignment 1", "weight": 20},
            {"name": "Quiz 1", "weight": 10},
            {"name": "Project", "weight": 20},
            {"name": "Final Exam", "weight": 50},
        ],
        "English": [
            {"name": "Portfolio", "weight": 30},
            {"name": "Speaking", "weight": 20},
            {"name": "Essay", "weight": 30},
            {"name": "Exam", "weight": 20},
        ],
        "Investigating Science": [
            {"name": "Prac Report", "weight": 25},
            {"name": "Research Task", "weight": 25},
            {"name": "In-class Task", "weight": 20},
            {"name": "Exam", "weight": 30},
        ],
    }
    
    if template_name not in templates:
        return jsonify({'error': 'Template not found'}), 404
    
    return jsonify({
        'name': template_name,
        'assessments': templates[template_name]
    })

# ===============================
# CSV TEMPLATE HELPERS
# ===============================

@app.route('/api/templates/student-csv', methods=['GET'])
def download_student_csv_template():
    """Generate and download a sample CSV template for student import"""
    try:
        # Sample CSV data
        csv_data = [
            ['student_id', 'first_name', 'last_name', 'email'],
            ['STU001', 'John', 'Smith', 'john.smith@school.edu'],
            ['STU002', 'Jane', 'Doe', 'jane.doe@school.edu'],
            ['STU003', 'Mike', 'Johnson', 'mike.johnson@school.edu'],
            ['STU004', 'Sarah', 'Wilson', 'sarah.wilson@school.edu'],
            ['STU005', 'David', 'Brown', 'david.brown@school.edu'],
        ]
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        for row in csv_data:
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        # Create response
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=student_import_template.csv'
        
        return response
        
    except Exception as e:
        app.logger.error(f"Error generating CSV template: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/import/info', methods=['GET'])
def get_import_info():
    """Get information about CSV import format and requirements"""
    return jsonify({
        'format': {
            'required_columns': ['student_id', 'first_name', 'last_name'],
            'optional_columns': ['email'],
            'column_order': ['student_id', 'first_name', 'last_name', 'email'],
            'encoding': 'UTF-8',
            'file_type': 'CSV'
        },
        'requirements': [
            'First row must contain column headers',
            'student_id must be unique',
            'first_name and last_name are required',
            'email is optional but must be valid if provided',
            'File must be saved in UTF-8 encoding'
        ],
        'examples': [
            {
                'student_id': 'STU001',
                'first_name': 'John',
                'last_name': 'Smith',
                'email': 'john.smith@school.edu'
            },
            {
                'student_id': 'STU002',
                'first_name': 'Jane',
                'last_name': 'Doe',
                'email': 'jane.doe@school.edu'
            }
        ]
    })

# ===============================
# HEALTH CHECK
# ===============================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0'
    })

# ===============================
# ERROR HANDLERS
# ===============================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ===============================
# DEVELOPMENT HELPERS
# ===============================

@app.route('/api/seed', methods=['POST'])
def seed_data():
    """Seed database with comprehensive sample data"""
    try:
        import random
        
        # Check if sample data already exists
        teachers = db.get_all_teachers()
        sample_emails = ['sarah.johnson@school.edu', 'michael.chen@school.edu', 'emily.davis@school.edu']
        if any(t['email'] in sample_emails for t in teachers):
            return jsonify({
                'message': 'Sample data already exists! You can see teachers, classes, and students in the interface.',
                'teachers': len([t for t in teachers if t['email'] in sample_emails]),
                'status': 'already_exists'
            })
        
        # Add sample teachers
        teacher1_id = db.add_teacher('Dr. Sarah Johnson', 'sarah.johnson@school.edu')
        teacher2_id = db.add_teacher('Prof. Michael Chen', 'michael.chen@school.edu')
        teacher3_id = db.add_teacher('Ms. Emily Davis', 'emily.davis@school.edu')
        
        # Add sample classes
        math_class_id = db.add_class(teacher1_id, 'Advanced Mathematics', 'Mathematics', '2024', 'Semester 1')
        english_class_id = db.add_class(teacher2_id, 'English Literature', 'English', '2024', 'Semester 1')
        science_class_id = db.add_class(teacher3_id, 'Physics Fundamentals', 'Physics', '2024', 'Semester 1')
        history_class_id = db.add_class(teacher2_id, 'World History', 'History', '2024', 'Semester 1')
        
        # Add sample students with more realistic data
        students = [
            ('STU001', 'Alice', 'Johnson', 'alice.johnson@student.edu'),
            ('STU002', 'Bob', 'Smith', 'bob.smith@student.edu'),
            ('STU003', 'Carol', 'Davis', 'carol.davis@student.edu'),
            ('STU004', 'David', 'Wilson', 'david.wilson@student.edu'),
            ('STU005', 'Emma', 'Brown', 'emma.brown@student.edu'),
            ('STU006', 'Frank', 'Miller', 'frank.miller@student.edu'),
            ('STU007', 'Grace', 'Taylor', 'grace.taylor@student.edu'),
            ('STU008', 'Henry', 'Anderson', 'henry.anderson@student.edu'),
        ]
        
        # Add students and enroll them in classes
        for student_id, first, last, email in students:
            db.add_student(student_id, first, last, email)
            # Enroll each student in 2-3 classes randomly
            classes = [math_class_id, english_class_id, science_class_id, history_class_id]
            enrolled_classes = random.sample(classes, random.randint(2, 3))
            for class_id in enrolled_classes:
                db.enroll_student_in_class(class_id, student_id)
        
        # Add comprehensive assessments for Math class
        math_assessments = [
            db.add_assessment(math_class_id, 'Assignment 1: Algebra', 20, '2024-03-15', 'Linear equations and inequalities'),
            db.add_assessment(math_class_id, 'Quiz 1: Functions', 10, '2024-03-20', 'Basic function concepts'),
            db.add_assessment(math_class_id, 'Midterm Exam', 25, '2024-04-15', 'Comprehensive midterm examination'),
            db.add_assessment(math_class_id, 'Assignment 2: Calculus', 20, '2024-04-25', 'Derivatives and limits'),
            db.add_assessment(math_class_id, 'Final Project', 25, '2024-05-15', 'Applied mathematics research project'),
        ]
        
        # Add assessments for English class
        english_assessments = [
            db.add_assessment(english_class_id, 'Essay 1: Poetry Analysis', 25, '2024-03-10', 'Analysis of romantic poetry'),
            db.add_assessment(english_class_id, 'Presentation: Shakespeare', 15, '2024-03-25', 'Character analysis presentation'),
            db.add_assessment(english_class_id, 'Midterm Exam', 30, '2024-04-10', 'Literature comprehension exam'),
            db.add_assessment(english_class_id, 'Final Essay', 30, '2024-05-10', 'Comparative literature essay'),
        ]
        
        # Add assessments for Science class
        science_assessments = [
            db.add_assessment(science_class_id, 'Lab Report 1', 20, '2024-03-12', 'Motion and forces experiment'),
            db.add_assessment(science_class_id, 'Quiz 1: Mechanics', 15, '2024-03-22', 'Newton\'s laws and applications'),
            db.add_assessment(science_class_id, 'Midterm Exam', 25, '2024-04-12', 'Physics fundamentals exam'),
            db.add_assessment(science_class_id, 'Lab Report 2', 20, '2024-04-28', 'Energy and momentum lab'),
            db.add_assessment(science_class_id, 'Final Project', 20, '2024-05-12', 'Physics demonstration project'),
        ]
        
        # Add realistic grades for students
        all_classes = [
            (math_class_id, math_assessments),
            (english_class_id, english_assessments),
            (science_class_id, science_assessments)
        ]
        
        for class_id, assessments in all_classes:
            students_data = db.get_class_students(class_id)
            for student in students_data:
                # Create different performance profiles for students
                student_performance = random.choice(['high', 'medium', 'low', 'mixed'])
                
                for i, assessment_id in enumerate(assessments):
                    # Leave some final assessments incomplete
                    if i < len(assessments) - 1 or random.random() > 0.3:
                        if student_performance == 'high':
                            score = random.randint(85, 98)
                        elif student_performance == 'medium':
                            score = random.randint(70, 84)
                        elif student_performance == 'low':
                            score = random.randint(55, 75)
                        else:  # mixed performance
                            score = random.randint(60, 95)
                        
                        db.update_student_grade(student['enrollment_id'], assessment_id, score)
        
        # Count created items
        teacher_count = 3
        class_count = 4
        student_count = len(students)
        
        return jsonify({
            'message': f'Sample data created successfully! Added {teacher_count} teachers, {class_count} classes, {student_count} students with realistic grades and assessments.',
            'teachers': teacher_count,
            'classes': class_count,
            'students': student_count
        })
        
    except Exception as e:
        app.logger.error(f"Error seeding data: {e}")
        return jsonify({'error': f'Seeding failed: {str(e)}'}), 500

if __name__ == '__main__':
    # Initialize database
    db.init_database()
    
    # Run the application
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000
    )