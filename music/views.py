from __future__ import unicode_literals
from django.contrib.auth import authenticate, login
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import logout
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from .models import Album, Song
from .forms import AlbumForm, SongForm, UserForm, DownloadForm
# import youtube_dl
import re
AUDIO_FILE_TYPES = ['wav', 'mp3', 'ogg']
IMAGE_FILE_TYPES = ['png', 'jpg', 'jpeg']

def index(request):
    if not request.user.is_authenticated:
        return render(request, 'music/login.html')
    else:
        albums = Album.objects.filter(user=request.user)
        song_results = Song.objects.all()
        query = request.GET.get("q")
        if query:
            albums = albums.filter(
                Q(album_title__icontains=query) |
                Q(artist__icontains=query)
            ).distinct()
            song_results = song_results.filter(
                Q(song_title__icontains=query)
            ).distinct()
            return render(request, 'music/index.html', {
                'albums': albums,
                'songs': song_results,
            })
        else:
            return render(request, 'music/index.html', {'albums': albums})


def login_user(request):

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)

        if user is not None:
          if user.is_active:
              login(request, user)
              albums = Album.objects.filter(user=request.user)
              return render(request,'music/index.html',{'albums': albums})
          else:
              return render(request, 'music/login.html', {'error_message': 'Your account has been disabled'})
        else:
            return render(request, 'music/login.html', {'error_message': 'Invalid login'})
    return render(request, 'music/login.html')


def detail(request, album_id):

    if not request.user.is_authenticated:
        return render(request, 'music/login.html')
    else:
        user = request.user
        album = get_object_or_404(Album, pk=album_id)
        return render(request, 'music/detail.html', {'album': album, 'user': user})


def favorite(request, song_id):

    song = get_object_or_404(Song, pk=song_id)
    try:
        if song.is_favorite:
            song.is_favorite = False
        else:
            song.is_favorite = True
        song.save()
    except (KeyError, Song.DoesNotExist):
        return JsonResponse({'success': False})
    else:
        return JsonResponse({'success': True})


def favorite_album(request, album_id):

    album = get_object_or_404(Album, pk=album_id)
    try:
        if album.is_favorite:
            album.is_favorite = False
        else:
            album.is_favorite = True
        album.save()
    except (KeyError, Album.DoesNotExist):
        return JsonResponse({'success': False})
    else:
        return JsonResponse({'success': True})


def songs(request, filter_by):

    if not request.user.is_authenticated:
        return render(request, 'music/login.html')
    else:
        try:
            song_ids = []
            for album in Album.objects.filter(user=request.user):
                for song in album.song_set.all():
                    song_ids.append(song.pk)
            users_songs = Song.objects.filter(pk__in=song_ids)
            if filter_by == 'favorites':
                users_songs = users_songs.filter(is_favorite=True)
        except Album.DoesNotExist:
            users_songs = []
        return render(request, 'music/songs.html', {
            'song_list': users_songs,
            'filter_by': filter_by,
        })


def logout_user(request):

    logout(request)
    form = UserForm(request.POST or None)
    context = {
        "form": form,
    }
    return render(request, 'music/login.html', context)


def register(request):

    form = UserForm(request.POST or None)
    if form.is_valid():
        user = form.save(commit=False)
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user.set_password(password)
        user.save()
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                albums = Album.objects.filter(user=request.user)
                return render(request, 'music/index.html', {'albums': albums})
    context = {
        "form": form,
    }
    return render(request, 'music/register.html', context)


def create_album(request):

    if not request.user.is_authenticated:
        return render(request, 'music/login.html')
    else:
        form = AlbumForm(request.POST or None, request.FILES or None)
        if form.is_valid():
            album = form.save(commit=False)
            album.user = request.user
            album.album_logo = request.FILES['album_logo']
            file_type = album.album_logo.url.split('.')[-1]
            file_type = file_type.lower()
            if file_type not in IMAGE_FILE_TYPES:
                context = {
                    'album': album,
                    'form': form,
                    'error_message': 'The image must be PNG, JPG or JPEG'
                }
                return render(request, 'music/create_album.html', context)
            album.save()
            return render(request,'music/detail.html',{'album': album})
        context = {
            "form": form
        }
        return render(request, 'music/create_album.html', context)


def create_song(request, album_id):

    form = SongForm(request.POST or None, request.FILES or None)
    album = get_object_or_404(Album, pk=album_id)
    if form.is_valid():
        albums_songs = album.song_set.all()
        for s in albums_songs:
            if s.song_title == form.cleaned_data.get("song_title"):
                context = {
                    'album': album,
                    'form': form,
                    'error_message': 'You already added that song',
                }
                return render(request, 'music/create_song.html', context)
        song = form.save(commit=False)
        song.album = album
        song.audio_file = request.FILES['audio_file']
        file_type = song.audio_file.url.split('.')[-1]
        file_type = file_type.lower()
        if file_type not in AUDIO_FILE_TYPES:
            context = {
                'album': album,
                'form': form,
                'error_message': 'Audio file must be WAV, MP3, or OGG',
            }
            return render(request, 'music/create_song.html', context)

        song.save()
        return render(request, 'music/detail.html', {'album': album})
    context = {
        'album': album,
        'form': form,
    }
    return render(request, 'music/create_song.html', context)


def delete_album(request, album_id):

    album = Album.objects.get(pk=album_id)
    album.delete()
    albums = Album.objects.filter(user=request.user)
    return render(request, 'music/index.html', {'albums': albums})


def delete_song(request, album_id, song_id):

    album = get_object_or_404(Album, pk=album_id)
    song = Song.objects.get(pk=song_id)
    song.delete()
    return render(request, 'music/detail.html', {'album': album})

# def download_video(request):
#     global context
#     form = DownloadForm(request.POST or None)

#     if form.is_valid():
#         video_url = form.cleaned_data.get("url")
#         regex = r'^(http(s)?:\/\/)?((w){3}.)?youtu(be|.be)?(\.com)?\/.+'
#         if not re.match(regex,video_url):
#             return HttpResponse('Enter correct url.')

#         ydl_opts = {}
#         download_mp3(video_url)
#         try:
#             with youtube_dl.YoutubeDL(ydl_opts) as ydl:
#                 meta = ydl.extract_info(
#                     video_url, download=False)
#             video_audio_streams = []
#             for m in meta['formats']:
#                 file_size = m['filesize']
#                 if file_size is not None:
#                     file_size = str(round(int(file_size) / 1000000,2))+"mb"

#                 resolution = 'Audio'
#                 if m['height'] is not None:
#                     resolution = str(m['height'])+"x"+str(m['width'])
#                 video_audio_streams.append({
#                     'resolution': resolution,
#                     'extension': m['ext'],
#                     'file_size': file_size,
#                     'video_url': m['url']
#                 })
#             video_audio_streams = video_audio_streams[::-1]
#             context = {
#                 'form': form,
#                 'title': meta.get('title', None),
#                 'streams': video_audio_streams,
#                 'description': meta.get('description'),
#                 'likes': int(meta.get("like_count", 0)),
#                 'dislikes': int(meta.get("dislike_count", 0)),
#                 'thumb': meta.get('thumbnails')[3]['url'],
#                 'duration': round(int(meta.get('duration', 1))/60, 2),
#                 'views': int(meta.get("view_count"))
#             }
#             print(context)
#             return render(request, 'music/downloader.html', context)
#         except Exception as error:
#             return HttpResponse(error.args[0])
#     return render(request, 'music/downloader.html', {'form': form})

# def download_mp3(url):
#     video_info = youtube_dl.YoutubeDL().extract_info(url=url, download = False)
#     options = {
#     "format": 'bestaudio/best',
#     "keepvideo": False,
#     'outtmpl': str(video_info["title"])+'.mp3'
#     }
#     with youtube_dl.YoutubeDL(options) as ydl:
#         ydl.download([video_info["webpage_url"]])