from django.db import models
from django.contrib.auth.hashers import make_password

class Staff(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        # Hash password before saving
        if not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        super(Staff, self).save(*args, **kwargs)

    def __str__(self):
        return self.name