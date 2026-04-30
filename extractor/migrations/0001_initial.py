from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='AuthToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.TextField()),
                ('captured_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Token JD',
                'verbose_name_plural': 'Tokens JD',
                'ordering': ['-captured_at'],
            },
        ),
        migrations.CreateModel(
            name='RunLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('total_chassis', models.IntegerField(default=0)),
                ('inserted', models.IntegerField(default=0)),
                ('errors', models.IntegerField(default=0)),
                ('detail', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'Log de Execução',
                'verbose_name_plural': 'Logs de Execução',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='StageChassi',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pin', models.CharField(max_length=50, unique=True)),
                ('source', models.CharField(default='api', max_length=100)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pendente'),
                        ('processing', 'Processando'),
                        ('done', 'Concluído'),
                        ('error', 'Erro'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('error_msg', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'Chassi em Stage',
                'verbose_name_plural': 'Chassis em Stage',
                'ordering': ['-added_at'],
            },
        ),
    ]
