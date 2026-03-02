"""
Patient Notification Service
Handles sending notifications from facilities back to patients
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import send_mail
import requests

from ..models import FacilityRouting, Facility, FacilityNotification
from ..models_patient_notifications import PatientNotification, PatientNotificationPreference

logger = logging.getLogger(__name__)


class PatientNotificationService:
    """
    Service for sending notifications to patients about their case status
    Integrates with WhatsApp, SMS, and other communication channels
    """
    
    def __init__(self):
        self.default_channel = 'whatsapp'
        self.max_retries = 3
        self.timeout_seconds = 30
    
    def send_facility_confirmation_notification(
        self, 
        routing: FacilityRouting, 
        facility: Facility,
        beds_reserved: int = 0,
        additional_info: Optional[Dict] = None
    ) -> PatientNotification:
        """
        Send notification to patient when facility confirms their case
        """
        message_data = {
            'facility_name': facility.name,
            'facility_address': facility.address,
            'facility_phone': facility.phone_number,
            'facility_type': facility.get_facility_type_display(),
            'beds_reserved': beds_reserved,
            'patient_token': routing.patient_token,
            'risk_level': routing.get_risk_level_display(),
            'primary_symptom': routing.primary_symptom,
            'estimated_wait_time': additional_info.get('estimated_wait_time', '30 minutes') if additional_info else '30 minutes',
            'directions': additional_info.get('directions', '') if additional_info else '',
            'special_instructions': additional_info.get('special_instructions', '') if additional_info else '',
        }
        
        title = f"✅ {facility.name} Confirmed Your Case"
        message = self._generate_facility_confirmation_message(message_data)
        
        return self._create_and_send_notification(
            routing=routing,
            facility=facility,
            notification_type=PatientNotification.NotificationType.FACILITY_CONFIRMED,
            title=title,
            message=message,
            additional_data=message_data
        )
    
    def send_facility_rejection_notification(
        self, 
        routing: FacilityRouting, 
        facility: Facility,
        rejection_reason: str,
        alternative_facility: Optional[Facility] = None
    ) -> PatientNotification:
        """
        Send notification to patient when facility rejects their case
        """
        message_data = {
            'facility_name': facility.name,
            'rejection_reason': rejection_reason,
            'patient_token': routing.patient_token,
            'risk_level': routing.get_risk_level_display(),
            'primary_symptom': routing.primary_symptom,
            'alternative_facility_name': alternative_facility.name if alternative_facility else None,
            'alternative_facility_address': alternative_facility.address if alternative_facility else None,
            'next_steps': 'We are finding an alternative facility for you' if not alternative_facility else f'Your case has been sent to {alternative_facility.name}',
        }
        
        title = f"❌ {facility.name} Cannot Accept Your Case"
        message = self._generate_facility_rejection_message(message_data)
        
        return self._create_and_send_notification(
            routing=routing,
            facility=facility,
            notification_type=PatientNotification.NotificationType.FACILITY_REJECTED,
            title=title,
            message=message,
            additional_data=message_data
        )
    
    def send_alternative_facility_notification(
        self, 
        routing: FacilityRouting, 
        new_facility: Facility,
        reason_for_change: str = "Previous facility was unable to accept your case"
    ) -> PatientNotification:
        """
        Send notification to patient about alternative facility assignment
        """
        message_data = {
            'new_facility_name': new_facility.name,
            'new_facility_address': new_facility.address,
            'new_facility_phone': new_facility.phone_number,
            'new_facility_type': new_facility.get_facility_type_display(),
            'patient_token': routing.patient_token,
            'risk_level': routing.get_risk_level_display(),
            'primary_symptom': routing.primary_symptom,
            'reason_for_change': reason_for_change,
            'estimated_arrival_time': 'Within 1 hour',
        }
        
        title = f"🏥 New Facility Assignment: {new_facility.name}"
        message = self._generate_alternative_facility_message(message_data)
        
        return self._create_and_send_notification(
            routing=routing,
            facility=new_facility,
            notification_type=PatientNotification.NotificationType.ALTERNATIVE_FACILITY,
            title=title,
            message=message,
            additional_data=message_data
        )
    
    def send_bed_reservation_notification(
        self, 
        routing: FacilityRouting, 
        facility: Facility,
        bed_count: int,
        room_info: Optional[Dict] = None
    ) -> PatientNotification:
        """
        Send notification to patient when bed is reserved
        """
        message_data = {
            'facility_name': facility.name,
            'bed_count': bed_count,
            'room_number': room_info.get('room_number', '') if room_info else '',
            'floor': room_info.get('floor', '') if room_info else '',
            'patient_token': routing.patient_token,
            'check_in_time': room_info.get('check_in_time', 'Immediately') if room_info else 'Immediately',
        }
        
        title = f"🛏️ Bed Reserved at {facility.name}"
        message = self._generate_bed_reservation_message(message_data)
        
        return self._create_and_send_notification(
            routing=routing,
            facility=facility,
            notification_type=PatientNotification.NotificationType.BED_RESERVED,
            title=title,
            message=message,
            additional_data=message_data
        )
    
    def send_case_update_notification(
        self, 
        routing: FacilityRouting, 
        update_message: str,
        facility: Optional[Facility] = None
    ) -> PatientNotification:
        """
        Send general case update notification to patient
        """
        message_data = {
            'update_message': update_message,
            'patient_token': routing.patient_token,
            'risk_level': routing.get_risk_level_display(),
            'facility_name': facility.name if facility else 'Processing facility assignment',
            'current_status': routing.get_routing_status_display(),
        }
        
        title = f"📋 Case Update: {routing.patient_token[:8]}"
        message = self._generate_case_update_message(message_data)
        
        return self._create_and_send_notification(
            routing=routing,
            facility=facility,
            notification_type=PatientNotification.NotificationType.CASE_UPDATE,
            title=title,
            message=message,
            additional_data=message_data
        )
    
    def _create_and_send_notification(
        self,
        routing: FacilityRouting,
        facility: Optional[Facility],
        notification_type: str,
        title: str,
        message: str,
        additional_data: Optional[Dict] = None
    ) -> PatientNotification:
        """
        Create notification record and send it
        """
        # Get or create patient preferences
        preferences, created = PatientNotificationPreference.objects.get_or_create(
            patient_token=routing.patient_token,
            defaults={
                'preferred_channel': self.default_channel,
            }
        )
        
        # Check if patient wants this type of notification
        if not preferences.can_send_notification(notification_type):
            logger.info(f"Patient {routing.patient_token[:8]} has opted out of {notification_type} notifications")
            return None
        
        # Check quiet hours
        if preferences.is_in_quiet_hours():
            logger.info(f"Patient {routing.patient_token[:8]} is in quiet hours, deferring notification")
            # TODO: Queue for later delivery
            return None
        
        # Create notification record
        notification = PatientNotification.objects.create(
            patient_token=routing.patient_token,
            triage_session_id=routing.triage_session_id,
            routing=routing,
            facility=facility,
            notification_type=notification_type,
            title=title,
            message=message,
            delivery_channel=preferences.preferred_channel,
            additional_data=additional_data or {}
        )
        
        # Send notification
        try:
            success = self._send_notification_via_channel(notification, preferences)
            
            if success:
                notification.mark_sent()
                logger.info(f"Patient notification sent: {notification.id} to {routing.patient_token[:8]}")
            else:
                notification.mark_failed("Failed to send notification")
                logger.error(f"Failed to send patient notification: {notification.id}")
                
        except Exception as e:
            notification.mark_failed(str(e))
            logger.error(f"Error sending patient notification: {e}")
        
        return notification
    
    def _send_notification_via_channel(
        self, 
        notification: PatientNotification, 
        preferences: PatientNotificationPreference
    ) -> bool:
        """
        Send notification via the patient's preferred channel
        """
        channel = notification.delivery_channel
        
        if channel == 'whatsapp':
            return self._send_via_whatsapp(notification, preferences)
        elif channel == 'sms':
            return self._send_via_sms(notification, preferences)
        elif channel == 'email':
            return self._send_via_email(notification, preferences)
        elif channel == 'ussd':
            return self._send_via_ussd(notification, preferences)
        else:
            # Default to WhatsApp
            return self._send_via_whatsapp(notification, preferences)
    
    def _send_via_whatsapp(self, notification: PatientNotification, preferences: PatientNotificationPreference) -> bool:
        """
        Send notification via WhatsApp
        """
        try:
            # Import WhatsApp client
            from apps.messaging.whatsapp.whatsapp_client import WhatsAppClient
            
            client = WhatsAppClient()
            
            # Get patient phone number from triage session or preferences
            phone_number = preferences.phone_number
            if not phone_number:
                # Try to get from triage session
                from apps.triage.models import TriageSession
                try:
                    session = TriageSession.objects.get(patient_token=notification.patient_token)
                    phone_number = getattr(session, 'phone_number', None)
                except TriageSession.DoesNotExist:
                    pass
            
            if not phone_number:
                logger.error(f"No phone number found for patient {notification.patient_token[:8]}")
                return False
            
            # Format message for WhatsApp
            whatsapp_message = self._format_message_for_whatsapp(notification.message)
            
            # Send message
            result = client.send_message(
                to=phone_number,
                message=whatsapp_message,
                message_type='text'
            )
            
            return result.get('success', False)
            
        except Exception as e:
            logger.error(f"WhatsApp sending failed: {e}")
            return False
    
    def _send_via_sms(self, notification: PatientNotification, preferences: PatientNotificationPreference) -> bool:
        """
        Send notification via SMS
        """
        try:
            # Get phone number
            phone_number = preferences.phone_number
            if not phone_number:
                logger.error(f"No phone number found for patient {notification.patient_token[:8]}")
                return False
            
            # Format message for SMS (character limit)
            sms_message = self._format_message_for_sms(notification.message)
            
            # TODO: Implement SMS sending logic
            # This would integrate with an SMS gateway like Africa's Talking
            logger.info(f"SMS would be sent to {phone_number}: {sms_message[:100]}...")
            
            return True  # Placeholder
            
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
            return False
    
    def _send_via_email(self, notification: PatientNotification, preferences: PatientNotificationPreference) -> bool:
        """
        Send notification via email
        """
        try:
            if not preferences.email_address:
                logger.error(f"No email address found for patient {notification.patient_token[:8]}")
                return False
            
            # Send email
            send_mail(
                subject=notification.title,
                message=notification.message,
                from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@harakacare.com',
                recipient_list=[preferences.email_address],
                fail_silently=False,
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return False
    
    def _send_via_ussd(self, notification: PatientNotification, preferences: PatientNotificationPreference) -> bool:
        """
        Send notification via USSD (store for next USSD session)
        """
        try:
            # USSD notifications are stored and shown in next USSD session
            # TODO: Implement USSD notification storage
            logger.info(f"USSD notification stored for patient {notification.patient_token[:8]}")
            return True
            
        except Exception as e:
            logger.error(f"USSD notification failed: {e}")
            return False
    
    def _format_message_for_whatsapp(self, message: str) -> str:
        """
        Format message for WhatsApp with proper formatting
        """
        # Convert markdown-like formatting to WhatsApp format
        formatted = message.replace('**', '*').replace('__', '_')
        return formatted
    
    def _format_message_for_sms(self, message: str) -> str:
        """
        Format message for SMS with character limits
        """
        # Remove markdown formatting and limit to 160 characters
        clean_message = message.replace('**', '').replace('__', '').replace('*', '').replace('_', '')
        if len(clean_message) > 160:
            clean_message = clean_message[:157] + '...'
        return clean_message
    
    def _generate_facility_confirmation_message(self, data: Dict) -> str:
        """
        Generate facility confirmation message
        """
        message = f"""
🏥 **FACILITY CONFIRMED**

✅ {data['facility_name']} has confirmed your case and is ready to receive you.

📍 **Address:**
{data['facility_address']}

📞 **Phone:** {data['facility_phone']}

🏷️ **Facility Type:** {data['facility_type']}

⚠️ **Risk Level:** {data['risk_level']}

🔍 **Primary Symptom:** {data['primary_symptom']}

"""
        
        if data.get('beds_reserved', 0) > 0:
            message += f"🛏️ **Beds Reserved:** {data['beds_reserved']}\n\n"
        
        message += f"⏰ **Estimated Wait Time:** {data['estimated_wait_time']}\n\n"
        
        if data.get('directions'):
            message += f"🗺️ **Directions:** {data['directions']}\n\n"
        
        if data.get('special_instructions'):
            message += f"📋 **Special Instructions:** {data['special_instructions']}\n\n"
        
        message += f"""
🚨 **IMPORTANT:**
• Please proceed to the facility immediately
• Bring your patient token: {data['patient_token'][:8]}...
• Follow all facility protocols upon arrival

If you cannot reach the facility, please call them immediately.

Your health is important - don't delay seeking care!
        """.strip()
        
        return message
    
    def _generate_facility_rejection_message(self, data: Dict) -> str:
        """
        Generate facility rejection message
        """
        message = f"""
❌ **FACILITY UNABLE TO ACCEPT**

Unfortunately, {data['facility_name']} is unable to accept your case at this time.

📋 **Reason:** {data['rejection_reason']}

⚠️ **Risk Level:** {data['risk_level']}

🔍 **Primary Symptom:** {data['primary_symptom']}

"""
        
        if data.get('alternative_facility_name'):
            message += f"""
🏥 **Alternative Facility:**
{data['alternative_facility_name']}
📍 {data['alternative_facility_address']}

✅ Your case has been automatically sent to this facility.
"""
        else:
            message += f"""
🔄 **Next Steps:**
{data['next_steps']}

We are working to find the best available facility for you.
You will receive another notification shortly with the new facility details.
"""
        
        message += f"""

⏰ **Important:**
• Continue monitoring your symptoms
• If your condition worsens, seek emergency care immediately
• Keep your phone available for the next update

Your patient token: {data['patient_token'][:8]}...

We apologize for any inconvenience and are working to ensure you receive care quickly.
        """.strip()
        
        return message
    
    def _generate_alternative_facility_message(self, data: Dict) -> str:
        """
        Generate alternative facility assignment message
        """
        message = f"""
🏥 **NEW FACILITY ASSIGNMENT**

Your case has been reassigned to a new facility that can provide the care you need.

✅ **New Facility:** {data['new_facility_name']}

📍 **Address:**
{data['new_facility_address']}

📞 **Phone:** {data['new_facility_phone']}

🏷️ **Facility Type:** {data['new_facility_type']}

⚠️ **Risk Level:** {data['risk_level']}

🔍 **Primary Symptom:** {data['primary_symptom']}

📅 **Reason for Change:** {data['reason_for_change']}

⏰ **Estimated Arrival:** {data['estimated_arrival_time']}

🚨 **IMPORTANT:**
• Please proceed to the new facility immediately
• Bring your patient token: {data['patient_token'][:8]}...
• The new facility is expecting your arrival

If you need directions or have questions, call the facility directly.

Your health is our priority - we've found the best available care for you!
        """.strip()
        
        return message
    
    def _generate_bed_reservation_message(self, data: Dict) -> str:
        """
        Generate bed reservation message
        """
        message = f"""
🛏️ **BED RESERVED**

Good news! {data['facility_name']} has reserved a bed for you.

🏥 **Facility:** {data['facility_name']}

🛏️ **Beds Reserved:** {data['bed_count']}

"""
        
        if data.get('room_number'):
            message += f"📍 **Room:** {data['room_number']}\n"
        
        if data.get('floor'):
            message += f"🏢 **Floor:** {data['floor']}\n"
        
        message += f"""
⏰ **Check-in Time:** {data['check_in_time']}

🎫 **Patient Token:** {data['patient_token'][:8]}...

🚨 **IMPORTANT:**
• Proceed to the facility as soon as possible
• Go to the reception/registration desk
• Provide your patient token for check-in
• Follow the facility's admission process

The reserved bed will be held for you. If you're delayed, please call the facility.

Your comfort and care are our priority!
        """.strip()
        
        return message
    
    def _generate_case_update_message(self, data: Dict) -> str:
        """
        Generate general case update message
        """
        message = f"""
📋 **CASE UPDATE**

Hello! We have an update about your case.

🆔 **Patient Token:** {data['patient_token'][:8]}...

⚠️ **Risk Level:** {data['risk_level']}

📊 **Current Status:** {data['current_status']}

🏥 **Facility:** {data['facility_name']}

📝 **Update:**
{data['update_message']}

"""
        
        message += """
📱 **Next Steps:**
• Keep your phone available for further updates
• Follow any instructions provided
• Call the facility if you have questions

We're here to ensure you receive the best possible care!
        """.strip()
        
        return message
