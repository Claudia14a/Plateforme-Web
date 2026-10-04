from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from utilisateurs.models import ProfilEntreprise, ProfilEtudiant, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
  list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
  list_filter = ('role', 'is_staff', 'is_active')
  fieldsets = UserAdmin.fieldsets + (('Rôle', {'fields': ('role',)}),)
  add_fieldsets = UserAdmin.add_fieldsets + (('Rôle', {'fields': ('role',)}),)


@admin.register(ProfilEtudiant)
class ProfilEtudiantAdmin(admin.ModelAdmin):
  list_display = ('user', 'formation', 'niveau_etudes')


@admin.register(ProfilEntreprise)
class ProfilEntrepriseAdmin(admin.ModelAdmin):
  list_display = ('nom_entreprise', 'secteur', 'user')

  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == 'user':
      kwargs['queryset'] = User.objects.filter(role='ENTREPRISE')
    return super().formfield_for_foreignkey(db_field, request, **kwargs)