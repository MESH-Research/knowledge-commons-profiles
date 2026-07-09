from django.db import migrations

SINGLETON_PK = 1


def create_maintenance_mode(apps, schema_editor):
    MaintenanceMode = apps.get_model("cilogon", "MaintenanceMode")
    MaintenanceMode.objects.get_or_create(pk=SINGLETON_PK)


def remove_maintenance_mode(apps, schema_editor):
    MaintenanceMode = apps.get_model("cilogon", "MaintenanceMode")
    MaintenanceMode.objects.filter(pk=SINGLETON_PK).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cilogon", "0015_maintenancemode"),
    ]

    operations = [
        migrations.RunPython(
            create_maintenance_mode,
            remove_maintenance_mode,
        ),
    ]
