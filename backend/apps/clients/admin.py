from django.contrib import admin

from .models import Agency, Client, ClientContact

admin.site.register(Client)
admin.site.register(ClientContact)
admin.site.register(Agency)
