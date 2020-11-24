from django.shortcuts import render, redirect
from .models import Video
from .forms import VideoForm, SearchForm
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models.functions import Lower

# Create your views here.

# Seriously, is the trick here that every django view function is run twice?
# Like, once on first access of the page, and then again when the submit button
# is hit? I feel like there's a way to tell that by watching the terminal...

def home(request):
    app_name = 'video collection'
    return render(request, 'video_collection/home.html', {'app_name': app_name})

def add(request):
    # doesn't initially run because it's not a POST yet?
    if request.method == 'POST':
        new_video_form = VideoForm(request.POST)
        if new_video_form.is_valid():
            try:
                new_video_form.save()
                return redirect('video_list')
            except ValidationError:
                messages.warning(request, 'Invalid YouTube URL')
            except IntegrityError:
                messages.warning(request, 'You already added that video')

        messages.warning(request, 'Check the data entered')
        return render(request, 'video_collection/add.html', {'new_video_form': new_video_form})
    # Which means this runs first, creating the video form from the model and then rendering it
    # on the html page making the request.. 
    new_video_form = VideoForm()
    return render(request, 'video_collection/add.html', {'new_video_form': new_video_form})

def video_list(request):
    # getting the form...
    search_form = SearchForm(request.GET)
    # initially not valid cause not entered.. so down to the bottom
    if search_form.is_valid():
        # then back here, once they click submit again, it takes the search term and cleans it?
        # I have to read up more on that function.
        # then uses it to find the video objects in the database. this is django's ORM I think?
        search_term = search_form.cleaned_data['search_term']
        videos = Video.objects.filter(name__icontains=search_term).order_by(Lower('name'))

    else:
        search_form = SearchForm()
        videos = Video.objects.order_by(Lower('name'))
    # so the page returns the render for the search form and videos to the page..
    return render(request, 'video_collection/video_list.html', {'videos': videos, 'search_form': search_form})

