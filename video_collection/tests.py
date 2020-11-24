from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Video

class TestHomePageMessage(TestCase):

    def test_app_title_message_shown_on_home_page(self):
        url = reverse('home')
        response = self.client.get(url)
        self.assertContains(response, 'collection')

class TestAddVideos(TestCase):
    # add video, add to db, and video id created

    def test_add_video(self):
        add_video_url = reverse('add_video')

        valid_video = {
            'name': 'test',
            'url': 'https://www.youtube.com/watch?v=aGCdLKXNF3w',
            'notes': 'music video'
        }

        # follow=True needed because view redirects to vid list after successfully adding
        response = self.client.post(add_video_url, data=valid_video, follow=True)

        # redirect to vid list
        self.assertTemplateUsed('video_collection/video_list.html')

        # video list has new video
        self.assertContains(response, 'test')
        self.assertContains(response, 'https://www.youtube.com/watch?v=aGCdLKXNF3w')
        self.assertContains(response, 'music video')

        # vid count on page is correct
        self.assertContains(response, '1 video')
        self.assertNotContains(response, '1 videos')

        # one new video in the database
        video_count = Video.objects.count()
        self.assertEqual(1, video_count)

        # get that video if there's 1, then it's that
        video = Video.objects.first()

        self.assertEqual('test', video.name)
        self.assertEqual('https://www.youtube.com/watch?v=aGCdLKXNF3w', video.url)
        self.assertEqual('music video', video.notes)
        self.assertEqual('aGCdLKXNF3w', video.video_id)

        # add another video and check both
        valid_video_2 = {
            'name': 'another vid',
            'url': 'https://www.youtube.com/watch?v=u7APmRkatEU',
            'notes': 'a second music video'
        }

        # again need follow=True to go through redirect
        response = self.client.post(add_video_url, data=valid_video_2, follow=True)

        self.assertTemplateUsed('video_collection/video_list.html')
        self.assertContains(response, '2 videos')

        # vid 1
        self.assertContains(response, 'test')
        self.assertContains(response, 'https://www.youtube.com/watch?v=aGCdLKXNF3w')
        self.assertContains(response, 'music video')

        # vid 2
        self.assertContains(response, 'another vid')
        self.assertContains(response, 'https://www.youtube.com/watch?v=u7APmRkatEU')
        self.assertContains(response, 'a second music video')

        # db contains two
        self.assertEqual(2, Video.objects.count())

        # are both present on page? way to check is a query for a video with the expected data
        # get method will raise a DoesNotExist error if a matching video is not found and will cause test to fail

        video_1_in_db = Video.objects.get(name='test', url='https://www.youtube.com/watch?v=aGCdLKXNF3w', \
            notes='music video', video_id='aGCdLKXNF3w')
        
        video_2_in_db = Video.objects.get(name='another vid', url='https://www.youtube.com/watch?v=u7APmRkatEU', \
            notes='a second music video', video_id='u7APmRkatEU')

        # correct videos in the context?
        # object in the response is from db query, so it's a QuerySet object, convert to list
        videos_in_context = list(response.context['videos']) 

        expected_vids_in_context = [video_2_in_db, video_1_in_db] # order sorted by name
        self.assertEqual(expected_vids_in_context, videos_in_context)

    # notes optional
    def test_add_video_no_notes_vid_added(self):
        add_video_url = reverse('add_video')

        valid_video = {
            'name': 'test',
            'url': 'https://www.youtube.com/watch?v=aGCdLKXNF3w',
            # no notes
        }

        response = self.client.post(add_video_url, data=valid_video, follow=True)

        self.assertTemplateUsed('video_collection/video_list.html')
        self.assertContains(response, 'test')
        self.assertContains(response, 'https://www.youtube.com/watch?v=aGCdLKXNF3w')
        self.assertContains(response, '1 video')
        self.assertNotContains(response, '1 videos')
        video_count = Video.objects.count()
        self.assertEqual(1, video_count)

        video = Video.objects.first()
        self.assertEqual('test', video.name)
        self.assertEqual('https://www.youtube.com/watch?v=aGCdLKXNF3w', video.url)
        self.assertEqual('', video.notes)
        self.assertEqual('aGCdLKXNF3w', video.video_id)


    # invalid videos not added
    def test_add_video_missing_fields(self):
        add_video_url = reverse('add_video')

        invalid_videos = [
            {
                'name': '', # empty name
                'url': 'https://www.youtube.com/watch?v=aGCdLKXNF3w',
                'notes': 'some vid'
            },
            {
                # no name field
                'url': 'https://www.youtube.com/watch?v=aGCdLKXNF3w',
                'notes': 'some vid'
            },
            {
                'name': 'test',
                'url': '', # empty url
                'notes': 'some vid'
            },
            {
                'name': 'test',
                # no url field
                'notes': 'some vid'
            },
            {
                'name': '', # empty name
                'url': '', # empty url
                'notes': 'some vid'
            },
            {
                # no name field
                # no url field
                'notes': 'some vid'
            }
        ]


        for invalid_video in invalid_videos:
            # follow=true NOT needed because it won't go anywhere, just simple response
            response = self.client.post(add_video_url, data=invalid_video)

        self.assertTemplateUsed('video_collection/add_video.html') # check still on add page
        self.assertEqual(0, Video.objects.count()) # no vids in db
        messages = response.context['messages'] # get messages
        message_texts = [ message.message for message in messages ] # get message texts
        self.assertIn('Check the data entered', message_texts) # is text in the messages?

        # can also check displayed message
        self.assertContains(response, 'Check the data entered')

    # duplicates not allowed
    
    def test_add_duplicate_video_not_added(self):
        # since integrity error is raised, the database has to be rolled back to the state before
        # this action (like duplicating a vid) was attempted. this is a separate transaction so the 
        # database might be in a weird state and future queries in this method can fail without
        # atomic transaction errors.
        # solution is to ensure the entire transaction is in an atomic block so the attempted save
        # and subsequent rollback are completely finished before more db transactions - like count query

        # most is handled automatically in a view function, but have to deal with it here.

        with transaction.atomic():
            new_video = {
                'name': 'test',
                'url': 'https://www.youtube.com/watch?v=aGCdLKXNF3w',
                'notes': 'music video'
            }

            # create a video with this data in the database
            # the ** syntax unpacks the dictionary and converts it into function arguments
            # https://python-reference.readthedocs.io/en/latest/docs/operators/dict_unpack.html
            # Video.objects.create(**new_video)
            # with the new_video dictionary above is equivalent to
            # Video.objects.create(such and such)
            Video.objects.create(**new_video)
            video_count = Video.objects.count()
            self.assertEqual(1, video_count)
        
        with transaction.atomic():
            # try to create again
            response = self.client.post(reverse('add_video'), data=new_video)

            # same template, the add form
            self.assertTemplateUsed('video_collection/add.html')

            messages = response.context['messages']
            message_texts = [ message.message for message in messages ]
            self.assertIn('You already added that video', message_texts)

            self.assertContains(response, 'You already added that video')

        video_count = Video.objects.count()
        self.assertEqual(1, video_count)

    
    def test_add_video_invalid_url_not_added(self):

        # what other invalid strings shouldn't be allowed?

        invalid_video_urls = [
            'https://www.youtube.com/watch',
            'https://www.youtube.com/watch/somethingelse',
            'https://www.youtube.com/watch/somethingelse?v=1234567',
            'https://www.youtube.com/watch?',
            'https://www.youtube.com/watch?abc=123',
            'https://www.youtube.com/watch?v=',
            'https://github.com',
            '12345678',
            'hhhhhhhhttps://www.youtube.com/watch',
            'http://www.youtube.com/watch/somethingelse?v=1234567',
            'https://minneapolis.edu'
            'https://minneapolis.edu?v=123456'
            '',
            '    sdfsdf sdfsdf   sfsdfsdf',
            '    https://minneapolis.edu?v=123456     ',
            '[',
            '☂️🌟🌷',
            '!@#$%^&*(',
            '//',
            'file://sdfsdf',
        ]

        for invalid_url in invalid_video_urls:

            new_video = {
                'name': 'title',
                'url': invalid_url,
                'notes': 'notes'
            }

            response = self.client.post(reverse('add_video'), data=new_video)

        self.assertTemplateUsed('video_collection/add.html')

        messages = response.context['messages']
        message_texts = [ message.message for message in messages ]
        self.assertIn('Check the data entered', message_texts)
        self.assertIn('Invalid YouTube URL', message_texts)

        self.assertContains(response, 'Check the data entered')
        self.assertContains(response, 'Invalid YouTube URL')

        video_count = Video.objects.count()
        self.assertEqual(0, video_count)


class TestVideoList(TestCase):

    # all videos shown on list page, sorted by name, case insensitive

    def test_all_videos_displayed_in_correct_order(self):
        v1 = Video.objects.create(name='XYZ', notes='example', url='https://www.youtube.com/watch?v=123')
        v2 = Video.objects.create(name='ABC', notes='example', url='https://www.youtube.com/watch?v=456')
        v3 = Video.objects.create(name='lmn', notes='example', url='https://www.youtube.com/watch?v=789')
        v4 = Video.objects.create(name='def', notes='example', url='https://www.youtube.com/watch?v=101')

        expected_video_order = [v2, v4, v3, v1]
        response = self.client.get(reverse('video_list'))
        videos_in_template = list(response.context['videos'])
        self.assertEqual(expected_video_order, videos_in_template)

    def test_no_video_message(self):
        response = self.client.get(reverse('video_list'))
        videos_in_template = response.context['videos']
        self.assertContains(response, 'No videos')
        self.assertEquals(0, len(videos_in_template))


    # 1 video vs 4 videos message

    def test_video_number_message_single_video(self):
        v1 = Video.objects.create(name='XYZ', notes='example', url='https://www.youtube.com/watch?v=123')
        response = self.client.get(reverse('video_list'))
        self.assertContains(response, '1 video')
        self.assertNotContains(response, '1 videos')   # check this, because '1 videos' contains '1 video'


    def test_video_number_message_multiple_videos(self):
        v1 = Video.objects.create(name='XYZ', notes='example', url='https://www.youtube.com/watch?v=123')
        v2 = Video.objects.create(name='ABC', notes='example', url='https://www.youtube.com/watch?v=456')
        v3 = Video.objects.create(name='uvw', notes='example', url='https://www.youtube.com/watch?v=789')
        v4 = Video.objects.create(name='def', notes='example', url='https://www.youtube.com/watch?v=101')

        response = self.client.get(reverse('video_list'))
        self.assertContains(response, '4 videos')


    # search only shows matching videos, partial case-insensitive matches

    def test_video_search_matches(self):
        v1 = Video.objects.create(name='ABC', notes='example', url='https://www.youtube.com/watch?v=456')
        v2 = Video.objects.create(name='nope', notes='example', url='https://www.youtube.com/watch?v=789')
        v3 = Video.objects.create(name='abc', notes='example', url='https://www.youtube.com/watch?v=123')
        v4 = Video.objects.create(name='hello aBc!!!', notes='example', url='https://www.youtube.com/watch?v=101')
        
        expected_video_order = [v1, v3, v4]
        response = self.client.get(reverse('video_list') + '?search_term=abc')
        videos_in_template = list(response.context['videos'])
        self.assertEqual(expected_video_order, videos_in_template)


    def test_video_search_no_matches(self):
        v1 = Video.objects.create(name='ABC', notes='example', url='https://www.youtube.com/watch?v=456')
        v2 = Video.objects.create(name='nope', notes='example', url='https://www.youtube.com/watch?v=789')
        v3 = Video.objects.create(name='abc', notes='example', url='https://www.youtube.com/watch?v=123')
        v4 = Video.objects.create(name='hello aBc!!!', notes='example', url='https://www.youtube.com/watch?v=101')
        
        expected_video_order = []  # empty list 
        response = self.client.get(reverse('video_list') + '?search_term=kittens')
        videos_in_template = list(response.context['videos'])
        self.assertEqual(expected_video_order, videos_in_template)
        self.assertContains(response, 'No videos')

class TestVideoModel(TestCase):

    def test_create_id(self):
        video = Video.objects.create(name='example', url='https://www.youtube.com/watch?v=IODxDxX7oi4')
        self.assertEqual('IODxDxX7oi4', video.video_id)


    def test_create_id_valid_url_with_time_parameter(self):
        # a video that is playing and paused may have a timestamp in the query
        video = Video.objects.create(name='example', url='https://www.youtube.com/watch?v=IODxDxX7oi4&ts=14')
        self.assertEqual('IODxDxX7oi4', video.video_id)


    def test_create_video_notes_optional(self):
        v1 = Video.objects.create(name='example', url='https://www.youtube.com/watch?v=67890')
        v2 = Video.objects.create(name='different example', notes='example', url='https://www.youtube.com/watch?v=12345')
        expected_videos = [v1, v2]
        database_videos = Video.objects.all()
        self.assertCountEqual(expected_videos, database_videos)  # check contents of two lists/iterables but order doesn't matter.


    def test_invalid_urls_raise_validation_error(self):
        invalid_video_urls = [
            'https://www.youtube.com/watch',
            'https://www.youtube.com/watch/somethingelse',
            'https://www.youtube.com/watch/somethingelse?v=1234567',
            'https://www.youtube.com/watch?',
            'https://www.youtube.com/watch?abc=123',
            'https://www.youtube.com/watch?v=',
            'https://www.youtube.com/watch?v1234',
            'https://github.com',
            '12345678',
            'hhhhhhhhttps://www.youtube.com/watch',
            'http://www.youtube.com/watch/somethingelse?v=1234567',
            'https://minneapolis.edu'
            'https://minneapolis.edu?v=123456'
            ''
        ]

        for invalid_url in invalid_video_urls:
            with self.assertRaises(ValidationError):
                Video.objects.create(name='example', url=invalid_url, notes='example notes')

        video_count = Video.objects.count()
        self.assertEqual(0, video_count)


    def test_duplicate_video_raises_integrity_error(self):
        Video.objects.create(name='example', url='https://www.youtube.com/watch?v=IODxDxX7oi4')
        with self.assertRaises(IntegrityError):
            Video.objects.create(name='example', url='https://www.youtube.com/watch?v=IODxDxX7oi4')

        