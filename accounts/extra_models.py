from accounts.models import User
from core.models import NoUserBaseModel
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from translator import get_text as _

class Profile(NoUserBaseModel):
    user = models.OneToOneField(User, related_name="profile", on_delete=models.DO_NOTHING, verbose_name=_('user'))
    first_name = models.CharField(max_length=50, verbose_name=_('first_name'),default='')
