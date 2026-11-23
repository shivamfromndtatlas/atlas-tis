from django.contrib import admin

from .models import OTPChallenge, PermissionSet, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "first_name", "last_name", "role", "is_active", "mfa_enabled", "last_login"]
    list_filter = ["role", "is_active", "mfa_enabled"]
    search_fields = ["email", "first_name", "last_name"]
    exclude = ["password", "mfa_secret"]


admin.site.register(PermissionSet)
admin.site.register(OTPChallenge)
