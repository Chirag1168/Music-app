from __future__ import unicode_literals
from django.contrib.auth import authenticate, login
from django.core.files import File
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import logout
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
import _thread
from .models import Album, Song
from .forms import AlbumForm, SongForm, UserForm, DownloadForm
from pytube import YouTube
import os
import re
import random
import cv2
import numpy as np
from time import sleep
from website.settings import BASE_DIR

AUDIO_FILE_TYPES = ['wav', 'mp3', 'ogg']
IMAGE_FILE_TYPES = ['png', 'jpg', 'jpeg']

def about_us(request):
    return render(request, 'music/about_us.html')

def login_face_html(request):
    return render(request, 'music/login_face.html')
    
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


def login_face(request):
    faceDetect = cv2.CascadeClassifier(BASE_DIR+'/ml/haarcascade_frontalface_default.xml')
    cam = cv2.VideoCapture(0)
    rec = cv2.face.LBPHFaceRecognizer_create()
    rec.read(BASE_DIR+'/ml/recognizer/trainingData.yml')
    getId = 0
    font = cv2.FONT_HERSHEY_SIMPLEX
    userId = 0
    for i in range(15):
        sleep(1)
        ret, img = cam.read()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = faceDetect.detectMultiScale(gray, 1.3, 5)
        for(x,y,w,h) in faces:
            cv2.rectangle(img,(x,y),(x+w,y+h), (0,255,0), 2)
            getId,conf = rec.predict(gray[y:y+h, x:x+w])
            print(conf)
            if conf>35:
                userId = getId
                cv2.putText(img, "Detected",(x,y+h), font, 2, (0,255,0),2)
            else:
                cv2.putText(img, "Unknown",(x,y+h), font, 2, (0,0,255),2)

        cv2.imshow("Face",img)
        if(cv2.waitKey(1) == ord('q')):
            break
        elif(userId != 0):
            cv2.waitKey(1000)
            cam.release()
            cv2.destroyAllWindows()
            break
    if userId == 0:
        return render(request, 'music/login_face.html', {'error_message': 'No Face Detected'})
    user_model = User.objects.get(id=userId)
    if request.method == "POST":
        if user_model is not None:
            if user_model.is_active:
                login(request, user_model)
                print("login")
                albums = Album.objects.filter(user=request.user)
                print(albums)
                return render(request,'music/index.html',{'albums': albums})
            else:
                return render(request, 'music/login.html', {'error_message': 'Your account has been disabled'})
        else:
            return render(request, 'music/login.html', {'error_message': 'Invalid login'})
    cam.release()
    cv2.destroyAllWindows()
    return render(request, 'music/login_face.html')


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
            # 'song_url' : users_songs[0].audio_file.url,
            # 'song_title': users_songs[0].song_title,
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
        # print(user.id)
        if create_dataset(user.id):
            _thread.start_new_thread( training, () )
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

def download_song(request, album_id):
    global context
    form = DownloadForm(request.POST or None)

    if form.is_valid():
        album = get_object_or_404(Album, pk=album_id)
        video_url = form.cleaned_data.get("url")
        regex = r'^(http(s)?:\/\/)?((w){3}.)?youtu(be|.be)?(\.com)?\/.+'
        if not re.match(regex,video_url):
            return HttpResponse('Enter correct url.')
        message = download_mp3(video_url,album)
        if message:
            return render(request, 'music/detail.html', {'album': album,'error_message':message})
        return render(request, 'music/detail.html', {'album': album})
        # except Exception as error:
        #     return HttpResponse(error.args[0])
    return render(request, 'music/downloader.html', {'form': form})

def download_mp3(url, album):
    yt = YouTube(url)
    video = yt.streams.filter(only_audio=True).first()
    destination = 'media/'
    out_file = video.download(output_path=destination)
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    title = str(base.split('/')[-1])
    try:
        os.rename(out_file, new_file)
    except:
        if Song.objects.get(song_title = title,album = album):
            return "Cannot Download Duplicate Song in same Album!!!!!"
        random_no = random.randrange(0, 10000, 3)
        new_file = base +"_"+str(random_no)+ '.mp3'
        title = str(base.split('/')[-1]) +"_"+str(random_no)
        os.rename(out_file, new_file)
    Song.objects.create(album = album,song_title = title)
    song_model = Song.objects.get(song_title = title)
    file =  open(new_file, 'rb')
    song_model.audio_file = File(file)
    song_model.save()


def create_dataset(id):
    faceDetect = cv2.CascadeClassifier(BASE_DIR+'/ml/haarcascade_frontalface_default.xml')
    cam = cv2.VideoCapture(0)
    sampleNum = 0
    print((BASE_DIR+'/ml/dataset/'+str(id)))
    os.makedirs(BASE_DIR+'/ml/dataset/'+str(id),exist_ok = True)
    while(True):
        ret, img = cam.read()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = faceDetect.detectMultiScale(gray, 1.3, 5)
        for(x,y,w,h) in faces:
            sampleNum = sampleNum+1
            cv2.imwrite(BASE_DIR+'/ml/dataset/'+str(id)+'/'+str(sampleNum)+'.jpg', gray[y:y+h,x:x+w])
            cv2.rectangle(img,(x,y),(x+w,y+h), (0,255,0), 2)
            cv2.waitKey(250)

        cv2.imshow("Face",img)
        cv2.waitKey(1)
        if(sampleNum>35):
            break

    cam.release()
    cv2.destroyAllWindows()
    return True

def face_detection(image):
    image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    haar_classifier = cv2.CascadeClassifier(BASE_DIR + '/ml/haarcascade_frontalface_default.xml')
    face = haar_classifier.detectMultiScale(image_gray)
    (x,y,w,h) = face[0]
    return image_gray[y:y+w, x:x+h], face[0]

def prepare_data(data_path):
    folders = os.listdir(data_path)
    labels = []
    faces = []
    for folder in folders:
        label = int(folder)
        training_images_path = data_path + '/' + folder
        print(training_images_path)
        for image in os.listdir(training_images_path):
            image_path = training_images_path + '/' + image
            print(image_path)
            training_image = cv2.imread(image_path)
            try: 
                face, bounding_box = face_detection(training_image)
                faces.append(face)
                labels.append(label)
            except:
                pass

    print ('Training Done')
    return faces, labels    

def training():
    data_path = BASE_DIR + '/ml/dataset'
    faces, labels = prepare_data(data_path)
    model = cv2.face.LBPHFaceRecognizer_create()
    model.train(faces, np.array(labels))
    model.save(BASE_DIR+'/ml/recognizer/trainingData.yml')

