from django.utils.safestring import mark_safe

from accounts.models import User
from core.models import NoUserBaseModel
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from translator import get_text as _


class Profile(NoUserBaseModel):
    user = models.OneToOneField(User, related_name="profile", on_delete=models.DO_NOTHING, verbose_name=_('user'))
    first_name = models.CharField(max_length=50, verbose_name=_('first_name'), null=True, blank=True)
    last_name = models.CharField(max_length=50, verbose_name=_('last_name'), null=True, blank=True)
    company = models.CharField(max_length=50, verbose_name=_('company'), null=True, blank=True)
    phone = models.CharField(max_length=20, verbose_name=_('phone'), null=True, blank=True)
    email = models.EmailField(max_length=50, verbose_name=_('email'), null=True, blank=True)
    website = models.URLField(max_length=50, verbose_name=_('website'), null=True, blank=True)
    avatar = models.ImageField(verbose_name=_('avatar'), null=True, blank=True)

    @property
    def avatar_symbol(self):
        if self.avatar:
            res = f"""
            <div class="symbol symbol-35px symbol-circle" data-bs-toggle="tooltip" aria-label="{self.first_name}" 
            data-bs-original-title="{self.first_name}" 
            data-kt-initialized="1">
				<img alt="Pic" src={self.avatar.url}">
			</div>
            """
        else:
            res = f"""
            <div class="symbol symbol-35px symbol-circle" data-bs-toggle="tooltip" aria-label="{self.first_name}" 
            data-bs-original-title="{self.first_name}" 
            data-kt-initialized="1">
				<span class="symbol-label bg-primary text-inverse-primary fw-bold">{self.first_name[:4]}</span>
			</div>
            """
        return mark_safe(res)

