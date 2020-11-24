from urllib import parse
from django.db import models
from django.core.exceptions import ValidationError

# Create your models here.

class Video(models.Model):
    name = models.CharField(max_length=200)
    url = models.CharField(max_length=400)
    notes = models.TextField(blank=True, null=True)
    video_id = models.CharField(max_length=40, unique=True)

    def save(self, *args, **kwargs):
        # checks for valid youtube url in form
        # https://www.youtube.com/watch?v=12345678
        # where ## are the ID
        # extract id from url, prevent save if not valid, or no id found
        try:
            url_components = parse.urlparse(self.url)

            if url_components.scheme != 'https':
                raise ValidationError(f'Invalid YouTube URL {self.url}')

            if url_components.netloc != 'www.youtube.com':
                raise ValidationError(f'Invalid YouTube URL {self.url}')

            if url_components.path != '/watch':
                raise ValidationError(f'Invalid YouTube URL {self.url}')

            query_string = url_components.query
            if not query_string:
                raise ValidationError(f'Invalid YouTube URL {self.url}')
            parameters = parse.parse_qs(query_string, strict_parsing=True)
            parameter_list = parameters.get('v')
            if not parameter_list: # empty string, no list
                raise ValidationError(f'Invalid YouTube URL parameters {self.url}')
            self.video_id = parameter_list[0]
        except ValueError as err:
            raise ValidationError(f'Unable to parse URL {self.url}') from err

        super().save(*args, **kwargs)

    def __str__(self):
        # string displayed in admin console when printing model object
        # return any useful string, truncate notes to max 200 char
        if not self.notes:
            notes = 'No notes'
        else:
            notes=self.notes[:200]
        return f'ID: {self.pk}, Name: {self.name}, URL: {self.url}, Notes: {self.notes[:200]}'
