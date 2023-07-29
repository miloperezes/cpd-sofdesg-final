from django.db import models
    
class Stock(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=30, unique=True)
    quantity = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
	    return self.name