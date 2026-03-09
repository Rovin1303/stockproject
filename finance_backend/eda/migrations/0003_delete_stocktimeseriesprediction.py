# Generated manually to remove deprecated time series model.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("eda", "0002_stocktimeseriesprediction"),
    ]

    operations = [
        migrations.DeleteModel(
            name="StockTimeSeriesPrediction",
        ),
    ]
