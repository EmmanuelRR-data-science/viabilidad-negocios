"""Versioned report services (v0).

Contains:
- reports_service: download URL generation and entitlement validation
- report_pdf_service: PDF compilation with ReportLab
- report_job_service: background task orchestration (analytics → FODA → PDF → S3/email)
"""
