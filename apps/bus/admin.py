from django.contrib import admin
from .models import BusOperator, BusRoute, BusSchedule, BusBooking

admin.site.register(BusOperator)
admin.site.register(BusRoute)
admin.site.register(BusSchedule)
admin.site.register(BusBooking)
