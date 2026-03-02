"""
Patient Notification Models
Tracks notifications sent from facilities back to patients
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class PatientNotification(models.Model):
    """
    Tracks notifications sent to patients about their case status
    """
    
    class NotificationType(models.TextChoices):
        FACILITY_CONFIRMED = 'facility_confirmed', 'Facility Confirmed'
        FACILITY_REJECTED = 'facility_rejected', 'Facility Rejected'
        ALTERNATIVE_FACILITY = 'alternative_facility', 'Alternative Facility'
        BED_RESERVED = 'bed_reserved', 'Bed Reserved'
        APPOINTMENT_SCHEDULED = 'appointment_scheduled', 'Appointment Scheduled'
        CASE_UPDATE = 'case_update', 'Case Update'
        REMINDER = 'reminder', 'Reminder'
    
    class DeliveryStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        DELIVERED = 'delivered', 'Delivered'
        FAILED = 'failed', 'Failed'
        READ = 'read', 'Read'
    
    # Patient and case information
    patient_token = models.CharField(
        'patient token',
        max_length=64,
        db_index=True,
        help_text='Anonymous patient identifier'
    )
    
    triage_session_id = models.CharField(
        'triage session ID',
        max_length=64,
        blank=True,
        null=True,
        help_text='Related triage session'
    )
    
    routing = models.ForeignKey(
        'FacilityRouting',
        on_delete=models.CASCADE,
        related_name='patient_notifications',
        help_text='Related facility routing'
    )
    
    # Notification details
    notification_type = models.CharField(
        'notification type',
        max_length=30,
        choices=NotificationType.choices,
        help_text='Type of notification'
    )
    
    title = models.CharField(
        'title',
        max_length=200,
        help_text='Notification title'
    )
    
    message = models.TextField(
        'message',
        help_text='Full notification message'
    )
    
    # Delivery information
    delivery_channel = models.CharField(
        'delivery channel',
        max_length=20,
        choices=[
            ('whatsapp', 'WhatsApp'),
            ('sms', 'SMS'),
            ('ussd', 'USSD'),
            ('email', 'Email'),
            ('web', 'Web'),
        ],
        default='whatsapp',
        help_text='How the notification was sent'
    )
    
    delivery_status = models.CharField(
        'delivery status',
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        help_text='Delivery status of the notification'
    )
    
    sent_at = models.DateTimeField(
        'sent at',
        null=True,
        blank=True,
        help_text='When the notification was sent'
    )
    
    delivered_at = models.DateTimeField(
        'delivered at',
        null=True,
        blank=True,
        help_text='When the notification was delivered'
    )
    
    read_at = models.DateTimeField(
        'read at',
        null=True,
        blank=True,
        help_text='When the notification was read'
    )
    
    # Error handling
    error_message = models.TextField(
        'error message',
        blank=True,
        help_text='Error message if delivery failed'
    )
    
    retry_count = models.PositiveIntegerField(
        'retry count',
        default=0,
        validators=[MaxValueValidator(5)],
        help_text='Number of delivery attempts'
    )
    
    # Facility information
    facility = models.ForeignKey(
        'Facility',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patient_notifications',
        help_text='Facility related to this notification'
    )
    
    # Additional data
    additional_data = models.JSONField(
        'additional data',
        default=dict,
        blank=True,
        help_text='Additional notification data'
    )
    
    # Timestamps
    created_at = models.DateTimeField('created at', auto_now_add=True)
    updated_at = models.DateTimeField('updated at', auto_now=True)
    
    class Meta:
        verbose_name = 'Patient Notification'
        verbose_name_plural = 'Patient Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient_token', 'created_at']),
            models.Index(fields=['delivery_status', 'created_at']),
            models.Index(fields=['notification_type', 'created_at']),
            models.Index(fields=['routing', 'notification_type']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.patient_token[:8]}"
    
    def mark_sent(self):
        """Mark notification as sent"""
        self.delivery_status = self.DeliveryStatus.SENT
        self.sent_at = timezone.now()
        self.save(update_fields=['delivery_status', 'sent_at'])
    
    def mark_delivered(self):
        """Mark notification as delivered"""
        self.delivery_status = self.DeliveryStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=['delivery_status', 'delivered_at'])
    
    def mark_read(self):
        """Mark notification as read"""
        self.delivery_status = self.DeliveryStatus.READ
        self.read_at = timezone.now()
        self.save(update_fields=['delivery_status', 'read_at'])
    
    def mark_failed(self, error_message):
        """Mark notification as failed"""
        self.delivery_status = self.DeliveryStatus.FAILED
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['delivery_status', 'error_message', 'retry_count'])
    
    @property
    def is_delivered_successfully(self):
        """Check if notification was delivered successfully"""
        return self.delivery_status in [self.DeliveryStatus.DELIVERED, self.DeliveryStatus.READ]


class PatientNotificationPreference(models.Model):
    """
    Stores patient notification preferences
    """
    
    patient_token = models.CharField(
        'patient token',
        max_length=64,
        unique=True,
        db_index=True,
        help_text='Anonymous patient identifier'
    )
    
    preferred_channel = models.CharField(
        'preferred channel',
        max_length=20,
        choices=[
            ('whatsapp', 'WhatsApp'),
            ('sms', 'SMS'),
            ('ussd', 'USSD'),
            ('email', 'Email'),
            ('any', 'Any'),
        ],
        default='whatsapp',
        help_text='Patient preferred notification channel'
    )
    
    phone_number = models.CharField(
        'phone number',
        max_length=20,
        blank=True,
        help_text='Patient phone number for notifications'
    )
    
    email_address = models.EmailField(
        'email address',
        blank=True,
        help_text='Patient email address for notifications'
    )
    
    # Notification preferences
    enable_facility_updates = models.BooleanField(
        'enable facility updates',
        default=True,
        help_text='Receive notifications about facility responses'
    )
    
    enable_appointment_reminders = models.BooleanField(
        'enable appointment reminders',
        default=True,
        help_text='Receive appointment reminders'
    )
    
    enable_case_updates = models.BooleanField(
        'enable case updates',
        default=True,
        help_text='Receive general case status updates'
    )
    
    quiet_hours_start = models.TimeField(
        'quiet hours start',
        blank=True,
        null=True,
        help_text='Start time for quiet hours (no notifications)'
    )
    
    quiet_hours_end = models.TimeField(
        'quiet hours end',
        blank=True,
        null=True,
        help_text='End time for quiet hours (no notifications)'
    )
    
    language_preference = models.CharField(
        'language preference',
        max_length=10,
        choices=[
            ('en', 'English'),
            ('sw', 'Swahili'),
            ('lg', 'Luganda'),
        ],
        default='en',
        help_text='Preferred notification language'
    )
    
    # Timestamps
    created_at = models.DateTimeField('created at', auto_now_add=True)
    updated_at = models.DateTimeField('updated at', auto_now=True)
    
    class Meta:
        verbose_name = 'Patient Notification Preference'
        verbose_name_plural = 'Patient Notification Preferences'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Preferences - {self.patient_token[:8]}"
    
    def can_send_notification(self, notification_type):
        """Check if patient wants to receive this type of notification"""
        if notification_type in ['facility_confirmed', 'facility_rejected', 'alternative_facility']:
            return self.enable_facility_updates
        elif notification_type == 'appointment_scheduled':
            return self.enable_appointment_reminders
        elif notification_type == 'case_update':
            return self.enable_case_updates
        return True
    
    def is_in_quiet_hours(self):
        """Check if current time is in quiet hours"""
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        current_time = timezone.now().time()
        if self.quiet_hours_start <= self.quiet_hours_end:
            return self.quiet_hours_start <= current_time <= self.quiet_hours_end
        else:
            # Overnight quiet hours (e.g., 22:00 to 07:00)
            return current_time >= self.quiet_hours_start or current_time <= self.quiet_hours_end
