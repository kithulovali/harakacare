# HarakaCare Agent Data Transmission Architecture

## Overview

This document describes the complete data flow between the three main agents in the HarakaCare system: **Patient**, **Triage Agent**, and **Facility Agent**. The system ensures seamless communication and real-time updates throughout the patient care journey.

## System Architecture

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│   Patient   │◄──►│ Triage Agent │◄──►│ Facility Agent│◄──►│ Healthcare  │
│ Interface   │    │              │    │              │    │ Facilities  │
└─────────────┘    └──────────────┘    └──────────────┘    └─────────────┘
       │                   │                   │                   │
       │                   │                   │                   │
    WhatsApp/SMS        REST API           REST API           API/Webhook
    USSD/Web            JSON Data          JSON Data          JSON Data
```

## 1. Patient → Triage Agent Data Flow

### 1.1 Initial Patient Contact

**Channels:** WhatsApp, SMS, USSD, Web Interface

**Input Methods:**
- **Conversational**: Free-text symptom description
- **Structured**: Step-by-step form completion
- **Hybrid**: Mix of both approaches

#### 1.1.1 Conversational Intake (WhatsApp/SMS)

**Endpoint:** `POST /api/v1/triage/conversational/`

**Request Payload:**
```json
{
  "message": "I have severe chest pain and difficulty breathing",
  "conversation_id": "PT-ABC123" || null,
  "channel": "whatsapp" | "sms" | "ussd" | "web"
}
```

**Response Payload:**
```json
{
  "status": "incomplete" | "complete",
  "action": "answer_questions" | "proceed_to_triage",
  "intent": "emergency" | "routine",
  "message": "🚨 EMERGENCY: Go to nearest health facility RIGHT NOW",
  "missing_fields": ["age_group", "sex"],
  "extracted_so_far": {
    "complaint_text": "severe chest pain and difficulty breathing",
    "complaint_group": "chest_pain",
    "age_group": "adult",
    "sex": "male",
    "severity": "severe",
    "location": "Kampala"
  },
  "patient_token": "PT-189EF96878374CA8",
  "red_flags_detected": false,
  "conversation_turns": 2
}
```

#### 1.1.2 Structured Intake (Web Interface)

**Endpoint:** `POST /api/v1/triage/start/`

**Request Payload:**
```json
{
  "patient_token": "optional-generated-token",
  "complaint_text": "patient symptom description",
  "age_group": "newborn" | "infant" | "child" | "adolescent" | "adult" | "elderly",
  "sex": "male" | "female" | "other",
  "district": "Kampala",
  "subcounty": "Central",
  "village": "Kampala City",
  "consent_medical_triage": true,
  "consent_data_sharing": true,
  "consent_follow_up": true
}
```

**Response Payload:**
```json
{
  "patient_token": "PT-5C19BEDD3B6D4B08",
  "message": "Use this token to submit triage data",
  "expires_in_minutes": 30
}
```

### 1.2 Triage Session Data Processing

**Endpoint:** `POST /api/v1/triage/{patient_token}/submit/`

**Complete Patient Data:**
```json
{
  "patient_token": "PT-5C19BEDD3B6D4B08",
  "complaint_text": "severe chest pain",
  "complaint_group": "chest_pain",
  "age_group": "adult",
  "sex": "male",
  "patient_relation": "self",
  "symptom_severity": "severe",
  "symptom_duration": "1_3_days",
  "progression_status": "worsening",
  "condition_occurrence": "sudden",
  "allergies_status": "none",
  "allergy_types": [],
  "chronic_conditions": [],
  "district": "Kampala",
  "subcounty": "Central",
  "village": "Kampala City",
  "pregnancy_status": "not_applicable",
  "has_chronic_conditions": false,
  "on_medication": false,
  "consent_medical_triage": true,
  "consent_data_sharing": true,
  "consent_follow_up": true,
  "vitals": {
    "heart_rate": 120,
    "blood_pressure": "160/90",
    "temperature": 38.5,
    "respiratory_rate": 24,
    "oxygen_saturation": 92
  }
}
```

**Triage Processing Response:**
```json
{
  "patient_token": "PT-5C19BEDD3B6D4B08",
  "risk_level": "high" | "medium" | "low",
  "follow_up_priority": "immediate" | "urgent" | "routine",
  "decision_basis": "Chest pain with vital signs abnormalities",
  "recommended_action": "seek_emergency_care" | "see_doctor" | "home_care",
  "facility_type": "hospital" | "clinic" | "urgent_care",
  "reasoning": "Patient presents with red flag symptoms requiring immediate attention",
  "disclaimers": ["This is not a substitute for professional medical advice"],
  "follow_up_required": true,
  "follow_up_timeframe": "immediately",
  "age_specific_note": "Adult patients with chest pain require immediate evaluation",
  "red_flags_detected": ["chest_pain", "difficulty_breathing", "abnormal_vitals"],
  "confidence_scores": {
    "risk_level": 0.9,
    "facility_type": 0.8,
    "urgency": 0.95
  }
}
```

## 2. Triage Agent → Facility Agent Data Flow

### 2.1 Case Forwarding to Facility Agent

**Internal Communication:** `AgentCommunicationTool.forward_to_facility_matching()`

**Payload to Facility Agent:**
```json
{
  "patient_token": "PT-5C19BEDD3B6D4B08",
  "triage_session_id": "TS-ABC123",
  "risk_level": "high",
  "follow_up_priority": "immediate",
  "follow_up_timeframe": "immediately",
  "symptom_summary": "Adult patient with severe chest pain and difficulty breathing",
  "has_red_flags": true,
  "district": "Kampala",
  "subcounty": "Central",
  "village": "Kampala City",
  "consent_follow_up": true,
  "facility_type_needed": "hospital",
  "urgency": "emergency",
  "is_emergency": true,
  "location": {
    "district": "Kampala",
    "latitude": 0.3476,
    "longitude": 32.5825,
    "distance_to_facility_km": null
  },
  "patient_demographics": {
    "age_group": "adult",
    "sex": "male",
    "primary_symptom": "chest_pain",
    "secondary_symptoms": ["difficulty_breathing"],
    "symptom_severity": "severe",
    "vital_signs": {
      "heart_rate": 120,
      "blood_pressure": "160/90",
      "temperature": 38.5
    }
  },
  "clinical_indicators": {
    "red_flags": ["chest_pain", "difficulty_breathing"],
    "risk_factors": [],
    "contraindications": []
  },
  "timestamp": "2026-03-02T09:15:30Z",
  "communication_priority": "high"
}
```

### 2.2 Facility Agent Processing

**Endpoint:** `POST /api/facilities/api/agent/`

**Facility Agent Response:**
```json
{
  "success": true,
  "routing_id": 123,
  "patient_token": "PT-5C19BEDD3B6D4B08",
  "booking_type": "automatic" | "manual",
  "candidates_found": 3,
  "recommendation": {
    "recommended_facility": {
      "id": 1,
      "name": "Kampala General Hospital",
      "facility_type": "hospital",
      "address": "123 Hospital Road, Kampala",
      "phone_number": "+256414123456",
      "distance_km": 2.5,
      "estimated_wait_time": "15 minutes",
      "available_beds": 5,
      "match_score": 0.95
    },
    "alternative_facilities": [
      {
        "id": 2,
        "name": "City Medical Center",
        "facility_type": "clinic",
        "address": "456 Clinic Street, Kampala",
        "distance_km": 4.2,
        "match_score": 0.85
      }
    ],
    "reason": "Closest hospital with emergency services and available beds",
    "booking_confirmed": true
  },
  "notifications_sent": 1,
  "patient_notification_sent": true
}
```

## 3. Facility Agent → Healthcare Facility Data Flow

### 3.1 Facility Notification Dispatch

**Method:** `NotificationDispatchTool.send_case_notification()`

**Notification to Facility:**
```json
{
  "notification_id": "notif_123_1",
  "timestamp": "2026-03-02T09:16:00Z",
  "notification_type": "new_case",
  "urgency": "emergency",
  "case": {
    "patient_token": "PT-5C19BEDD3B6D4B08",
    "triage_session_id": "TS-ABC123",
    "risk_level": "high",
    "primary_symptom": "chest_pain",
    "secondary_symptoms": ["difficulty_breathing"],
    "age_group": "adult",
    "sex": "male",
    "urgency": "emergency",
    "estimated_arrival": "within 30 minutes"
  },
  "location": {
    "district": "Kampala",
    "latitude": 0.3476,
    "longitude": 32.5825,
    "distance_to_facility_km": 2.5
  },
  "patient_summary": {
    "symptom_description": "Adult patient presenting with severe chest pain and difficulty breathing",
    "vital_signs": {
      "heart_rate": 120,
      "blood_pressure": "160/90",
      "temperature": 38.5,
      "respiratory_rate": 24,
      "oxygen_saturation": 92
    },
    "red_flags": ["chest_pain", "difficulty_breathing", "abnormal_vitals"],
    "recommended_action": "emergency_evaluation"
  },
  "facility_requirements": {
    "services_needed": ["emergency", "cardiology", "diagnostic"],
    "bed_type": "emergency",
    "specialist_needed": "cardiologist",
    "equipment_needed": ["ecg", "xray", "blood_tests"]
  },
  "response_required_by": "2026-03-02T09:20:00Z",
  "response_options": {
    "confirm": {
      "beds_available": true,
      "specialist_available": true,
      "estimated_wait_time": "15 minutes"
    },
    "reject": {
      "reason_required": true,
      "alternative_suggested": true
    }
  }
}
```

### 3.2 Facility Response Handling

**Endpoint:** `POST /api/facilities/api/agent/{routing_id}/facility_response/`

**Facility Response Payload:**
```json
{
  "facility_id": 1,
  "response_type": "confirm" | "reject",
  "response_data": {
    "confirm": {
      "beds_reserved": 1,
      "room_info": {
        "room_number": "ER-205",
        "floor": "2nd Floor",
        "bed_type": "emergency"
      },
      "estimated_wait_time": "15 minutes",
      "specialist_assigned": "Dr. John Smith - Cardiologist",
      "directions": "Enter through emergency entrance, ask for triage desk",
      "special_instructions": "Patient should bring ID and insurance information if available",
      "contact_person": "Nurse Sarah - +256414123456",
      "preparation_needed": ["ecg_machine", "blood_gas_analyzer", "iv_access_kit"]
    },
    "reject": {
      "reason": "Emergency department at capacity",
      "alternative_facility_suggested": 2,
      "estimated_wait_time_alternative": "45 minutes",
      "transfer_arranged": true,
      "reason_code": "capacity_full"
    }
  },
  "responded_by": "Dr. John Smith",
  "responded_at": "2026-03-02T09:18:30Z",
  "comments": "Patient sounds like potential cardiac emergency - prepare for immediate evaluation"
}
```

## 4. Facility Agent → Patient Data Flow (NEW!)

### 4.1 Patient Notification System

**Trigger:** Facility response (confirm/reject) or case updates

**Notification Service:** `PatientNotificationService`

#### 4.1.1 Facility Confirmation Notification

**Message Template:**
```
🏥 **FACILITY CONFIRMED**

✅ Kampala General Hospital has confirmed your case and is ready to receive you.

📍 **Address:**
123 Hospital Road, Kampala

📞 **Phone:** +256414123456

🏷️ **Facility Type:** Hospital

⚠️ **Risk Level:** High

🔍 **Primary Symptom:** Chest Pain

🛏️ **Beds Reserved:** 1

⏰ **Estimated Wait Time:** 15 minutes

🗺️ **Directions:** Enter through emergency entrance, ask for triage desk

📋 **Special Instructions:** Patient should bring ID and insurance information if available

🚨 **IMPORTANT:**
• Please proceed to the facility immediately
• Bring your patient token: PT-5C19BED...
• Follow all facility protocols upon arrival

If you cannot reach the facility, please call them immediately.

Your health is important - don't delay seeking care!
```

#### 4.1.2 Facility Rejection Notification

**Message Template:**
```
❌ **FACILITY UNABLE TO ACCEPT**

Unfortunately, Kampala General Hospital is unable to accept your case at this time.

📋 **Reason:** Emergency department at capacity

⚠️ **Risk Level:** High

🔍 **Primary Symptom:** Chest Pain

🏥 **Alternative Facility:**
City Medical Center
📍 456 Clinic Street, Kampala

✅ Your case has been automatically sent to this facility.

⏰ **Important:**
• Continue monitoring your symptoms
• If your condition worsens, seek emergency care immediately
• Keep your phone available for the next update

Your patient token: PT-5C19BED...

We apologize for any inconvenience and are working to ensure you receive care quickly.
```

#### 4.1.3 Bed Reservation Notification

**Message Template:**
```
🛏️ **BED RESERVED**

Good news! Kampala General Hospital has reserved a bed for you.

🏥 **Facility:** Kampala General Hospital

🛏️ **Beds Reserved:** 1

📍 **Room:** ER-205

🏢 **Floor:** 2nd Floor

⏰ **Check-in Time:** Immediately

🎫 **Patient Token:** PT-5C19BED...

🚨 **IMPORTANT:**
• Proceed to the facility as soon as possible
• Go to the reception/registration desk
• Provide your patient token for check-in
• Follow the facility's admission process

The reserved bed will be held for you. If you're delayed, please call the facility.

Your comfort and care are our priority!
```

### 4.2 Patient Notification Tracking

**Database Model:** `PatientNotification`

**Notification Record:**
```json
{
  "id": 1,
  "patient_token": "PT-5C19BEDD3B6D4B08",
  "triage_session_id": "TS-ABC123",
  "routing_id": 123,
  "facility_id": 1,
  "notification_type": "facility_confirmed",
  "title": "✅ Kampala General Hospital Confirmed Your Case",
  "message": "Full notification message content...",
  "delivery_channel": "whatsapp" | "sms" | "email" | "ussd",
  "delivery_status": "sent" | "delivered" | "read" | "failed",
  "sent_at": "2026-03-02T09:19:00Z",
  "delivered_at": "2026-03-02T09:19:15Z",
  "read_at": "2026-03-02T09:20:30Z",
  "error_message": null,
  "retry_count": 0,
  "additional_data": {
    "beds_reserved": 1,
    "room_number": "ER-205",
    "estimated_wait_time": "15 minutes"
  },
  "created_at": "2026-03-02T09:19:00Z",
  "updated_at": "2026-03-02T09:20:30Z"
}
```

### 4.3 Patient Preferences

**Database Model:** `PatientNotificationPreference`

**Preference Record:**
```json
{
  "id": 1,
  "patient_token": "PT-5C19BEDD3B6D4B08",
  "preferred_channel": "whatsapp",
  "phone_number": "+256987654321",
  "email_address": "patient@example.com",
  "enable_facility_updates": true,
  "enable_appointment_reminders": true,
  "enable_case_updates": true,
  "quiet_hours_start": "22:00:00",
  "quiet_hours_end": "07:00:00",
  "language_preference": "en" | "sw" | "lg",
  "created_at": "2026-03-02T09:15:00Z",
  "updated_at": "2026-03-02T09:15:00Z"
}
```

## 5. Complete Data Flow Summary

### 5.1 End-to-End Patient Journey

```
1. PATIENT INPUT
   ↓ WhatsApp/SMS/USSD/Web
2. TRIAGE AGENT
   ↓ Risk assessment & facility matching
3. FACILITY AGENT
   ↓ Find & notify suitable facilities
4. HEALTHCARE FACILITY
   ↓ Confirm/reject case
5. PATIENT NOTIFICATION
   ↓ Real-time status updates
6. PATIENT RECEIVES CARE
```

### 5.2 Data Transformation Pipeline

| Stage | Input Format | Processing | Output Format |
|-------|--------------|------------|---------------|
| Patient → Triage | Free text/structured forms | AI analysis, validation | Structured patient data |
| Triage → Facility | Structured patient data | Risk scoring, matching | Facility notification |
| Facility → Hospital | JSON notification | Human review | Confirm/reject response |
| Hospital → Patient | Facility response | Template generation | Patient notification |

### 5.3 Key Data Points Tracked

**Patient Data:**
- Demographics (age, sex, location)
- Symptoms (primary, secondary, severity)
- Vital signs (when available)
- Consent preferences
- Contact information

**Triage Data:**
- Risk level assessment
- Facility type requirements
- Urgency classification
- Red flag indicators
- Recommended actions

**Facility Data:**
- Capacity information
- Specialization matching
- Distance calculations
- Response times
- Bed availability

**Communication Data:**
- Message delivery status
- Patient preferences
- Notification history
- Response tracking

## 6. API Endpoints Summary

### 6.1 Patient-Facing Endpoints

```
POST /api/v1/triage/conversational/     # Conversational intake
POST /api/v1/triage/start/              # Generate patient token
POST /api/v1/triage/{token}/submit/     # Submit complete data
GET  /api/v1/triage/{token}/status/     # Check session status
GET  /api/v1/triage/health/             # Health check
```

### 6.2 Facility-Facing Endpoints

```
POST /api/facilities/api/agent/                    # Process triage case
POST /api/facilities/api/agent/{id}/facility_response/  # Facility response
GET  /api/facilities/api/agent/statistics/          # Agent statistics
POST /api/facilities/api/agent/update_capacity/     # Capacity updates
```

### 6.3 Internal Communication

```
AgentCommunicationLog     # Tracks inter-agent communication
PatientNotification       # Tracks patient notifications
FacilityNotification      # Tracks facility notifications
```

## 7. Error Handling & Retry Logic

### 7.1 Communication Failures

**Retry Strategy:**
- **Max retries:** 3 attempts per notification
- **Backoff:** Exponential (1s, 2s, 4s)
- **Failure handling:** Log error, mark as failed, try alternative channel

**Error Scenarios:**
- Facility not responding → Try alternative facility
- Patient unreachable → Try alternative channel
- Network timeout → Retry with backoff
- Invalid data → Return validation error

### 7.2 Data Validation

**Input Validation:**
- Required field checking
- Data type validation
- Range validation (vitals, age)
- Consent verification

**Output Validation:**
- Response format validation
- Required response fields
- Status code verification
- Error message formatting

## 8. Security & Privacy

### 8.1 Data Protection

- **Anonymous tokens:** Patient identifiers are anonymous
- **Consent management:** Explicit consent required for data sharing
- **Data minimization:** Only collect necessary health information
- **Encryption:** All communication encrypted in transit

### 8.2 Access Control

- **Role-based access:** Different permissions for different user types
- **API authentication:** Secure API access with tokens
- **Audit logging:** All data access logged
- **Data retention:** Configurable data retention policies

## 9. Monitoring & Analytics

### 9.1 Key Metrics

**Performance Metrics:**
- Response time (patient → triage)
- Processing time (triage → facility)
- Notification delivery time
- Facility response time

**Quality Metrics:**
- Triage accuracy
- Facility match success rate
- Patient satisfaction
- Notification delivery rate

### 9.2 Alerting

**System Alerts:**
- High error rates
- Slow response times
- Facility capacity issues
- Communication failures

**Clinical Alerts:**
- High-risk cases
- Red flag symptoms
- Emergency cases not responded to
- Patient deterioration indicators

---

## Conclusion

The HarakaCare agent data transmission system provides a comprehensive, real-time communication pipeline that ensures patients receive timely care while maintaining privacy and security. The system handles the complete journey from initial patient contact through facility assignment and ongoing care coordination.

Key strengths:
- **Real-time communication** across all stakeholders
- **Intelligent routing** based on clinical needs
- **Patient-centric notifications** keeping patients informed
- **Robust error handling** ensuring reliability
- **Scalable architecture** supporting growth

The system is designed to save lives by ensuring patients get the right care at the right time, with full transparency and communication throughout the process.
