from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from cloudant.client import Cloudant
import datetime
from config import CLOUDANTPASSWORD, CLOUDANTUSERNAME
import json
import re
import weasyprint
client = Cloudant(CLOUDANTUSERNAME, CLOUDANTPASSWORD, account=CLOUDANTUSERNAME)
client.connect()


# Create your views here.
@login_required(redirect_field_name='nextPage', login_url = '/login')
def home(request):
    DBAPPLICATIONS = client['applications']
    DBUSER = client['users']
    applicationList = DBAPPLICATIONS.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    applicationList1 = DBAPPLICATIONS.get_view_result('_design/fetch', 'byUsername')[:]
    for app in applicationList1:
        if request.user.username in app['value']['facultyList']:
            applicationList.append(app)
    for application in applicationList:
        application['class'] = application['id']
        application['id'] = "#" + application['id']
    # applicationList = [application1, application2, application3]
    user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    if user[0]['value']['designation'] == 'admin':
        return redirect('/admindashboard')
    notificationList = getNotification(request.user.username)
    return render(request, 'application/dashboard.html', {'user': user[0]['value'],
                                                          'applicationList': applicationList,
                                                          #'notificationList': notificationList[:6],
                                                          #'i': len(notificationList)
							})


@csrf_protect
def loginUser(request):
    if request.method == 'GET':
        return render(request, 'application/login.html')
    else:
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            DBUSER = client['users']
            userList = DBUSER.get_view_result('_design/fetch', 'byUsername')[username]
            login(request, user)
            if request.GET.get('nextPage', None) is not None:
                return redirect(request.GET.get('nextPage', None))
            if userList[0]['value']['designation'] == 'admin':
                return redirect('/admindashboard')
            else:
                return redirect('/dashboard')
        else:
            return render(request, 'application/login.html', {'msg': 'Invalid Username or Password'})


@csrf_exempt
def googleSignup(request):
    email = request.POST['email']
    DBUSER = client['users']
    newUser = DBUSER.get_view_result('_design/fetch', 'byEmail')[email]
    if len(newUser) != 0:
        # user already exists
        username = newUser[0]['value']['username']
        user = User.objects.get(username=username)
        DBUSER = client['users']
        userList = DBUSER.get_view_result('_design/fetch', 'byUsername')[username]
        login(request, user)
        if userList[0]['value']['designation'] == 'admin':
            return redirect('/admindashboard')
        else:
            return redirect('/dashboard')
    else:
        picUrl = request.POST['picUrl']
        fullName = request.POST['fullName']
        return render(request, 'application/signup.html', {'email': email, 'picUrl': picUrl, 'fullName': fullName})


@csrf_protect
def signup(request):
    if request.method == 'GET':
        return render(request, 'application/signup.html')
    else:
        username = request.POST['usernamesignup']
        email = request.POST['emailsignup']
        password = request.POST['passwordsignup']
        picUrl = request.POST['picUrl']
        fullName = request.POST['fullName']
        # Saving in sqlite
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            user.save()
        except Exception:
            return render(request, 'application/signup.html', {
                'msg': 'Username already exists',
                'email': email, 'picUrl': picUrl, 'fullName': fullName})
        # Saving in cloudant
        DBUSERS = client['users']
        newUser = {'username': username, 'email': email, 'picUrl': picUrl, 'fullName': fullName, 'designation': 'User'}
        DBUSERS.create_document(newUser)
        return redirect('/login')


@login_required(redirect_field_name='nextPage', login_url='/login')
def createApplication(request):
    if request.method == "GET":
        DBUSER = client['users']
        desigView = DBUSER.get_view_result('_design/fetch', 'byDesignation')
        facultyList = desigView['Faculty'][:]
        gymkhanaList = desigView['Gymkhana'][:]
        user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
        #notificationList = getNotification(request.user.username)
        return render(request, 'application/createApplication.html', {
            'user': user[0]['value'],
            'facultyList': facultyList,
            'gymkhanaList': gymkhanaList,
            'date': datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d'),
            # 'notificationList': notificationList[:6],
           # 'i': len(notificationList)

	})
        return HttpResponse("""WIP""")

    else:
        title = request.POST['title']
        appType = request.POST.get('type', 'General')
        status = 'Pending'
        dueDate = request.POST['dueDate']
        nextBy = request.POST.getlist('facultyList')[0]
        facultyList = request.POST.getlist('facultyList')
        subject = request.POST['subject'].strip()
        priority = request.POST['priority']
        author = request.user.username
        DBUSER = client['users']
        user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
        dateCreated = str(datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d, %H:%M %p'))
        newApplication = {'from': author, 'title': title, 'type': appType, 'status': status,
                          'dueDate': dueDate, 'nextBy': nextBy, 'subject': subject,
                          'facultyList': facultyList, 'dateCreated': dateCreated,
                          'picUrl': user[0]['value']['picUrl'], 'priority': priority}
        DBAPPLICATIONS = client['applications']
        DBACTIVITYLOG = client['activitylog']
        string = 'You created an application named ' + title + '.'
        dateCreated1 = str(datetime.datetime.strftime(datetime.datetime.now(), '%B %d, %Y, %H:%M %p'))
        DBACTIVITYLOG.create_document({'string': string, 'type': 'newapplication',
                                       'username': request.user.username,
                                       'date': dateCreated1})
        DBAPPLICATIONS.create_document(newApplication)
        applicationList = DBAPPLICATIONS.get_view_result('_design/fetch', 'byUsername')[request.user.username]
        for app in applicationList:
            if app['value']['dateCreated'] == dateCreated:
                appId = app['id']
        for faculty in facultyList:
            text = request.user.username + " sent a new application " + newApplication['title']
       #     addNotification(text, faculty,
        #                    "http://applicationrouting.eu-gb.mybluemix.net/applicationDetail/" + appId, "create")
        return redirect('/dashboard')
        # return HttpResponse("""WIP""")



def mainpage(request):
    if request.user.is_authenticated:
        return redirect('/dashboard')
    return render(request, 'application/main1.html')


@login_required(redirect_field_name='nextPage', login_url='/login')
def logoutUser(request):
    logout(request)
    return redirect('/')


@login_required(redirect_field_name='nextPage', login_url='/login')
def activitylog(request):
    return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def members(request):
    DBUSER = client['users']
    user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    memberList = DBUSER.get_view_result('_design/fetch', 'byUsername')[:]
    return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def applicationDetail(request, appId):
    if request.method == "GET":
        DBAPPLICATIONS = client['applications']
        try:
            application = DBAPPLICATIONS[appId]
        except Exception:
            return HttpResponse("""WIP""")
        DBUSER = client['users']
        user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
        DBCOMMENT = client['comments']
        commentList = DBCOMMENT.get_view_result('_design/fetch', 'byAppId')[appId]
        status = "hide"
        for faculty in application['facultyList']:
            if faculty == request.user.username and application['status'] == "Disapproved":
                status = "Disapproved"
                break
            elif request.user.username == application['nextBy']:
                status = "yourTurn"
                break
            elif request.user.username == faculty:
                status = "Approved"
                break
            elif faculty == application['nextBy']:
                break
        notificationList = getNotification(request.user.username)
        return HttpResponse("""WIP""")

@login_required(redirect_field_name='nextPage', login_url='/login')
def editProfile(request):
    if request.method == "GET":
        DBUSER = client['users']
        user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
        notificationList = getNotification(request.user.username)
        return HttpResponse("""WIP""")
    else:
        # Saving in cloudant
        DBUSER = client['users']
        user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
        user = DBUSER[user[0]['id']]
        user['collegeName'] = request.POST['collegename']
        user['password'] = request.POST['password']
        user['dob'] = request.POST['dob']
        user['gender'] = request.POST['gender']
        user['motto'] = request.POST['motto']
        user.save()
        DBACTIVITYLOG = client['activitylog']
        string = 'You edited your profile.'
        date = str(datetime.datetime.strftime(datetime.datetime.now(), '%B %d, %Y, %H:%M %p'))
        DBACTIVITYLOG.create_document({'string': string, 'type': 'editprofile',
                                       'username': request.user.username,
                                       'date': date})
        return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def profile(request):
    if request.method == "GET":
        DBUSER = client['users']
        user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
        notificationList = getNotification(request.user.username)
        return HttpResponse("""WIP""")

@login_required(redirect_field_name='nextPage', login_url='/login')
def faculty(request):
    DBUSER = client['users']
    user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    memberList = DBUSER.get_view_result('_design/fetch', 'byDesignation')['Faculty'][:]
    return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def gymkhana(request):
    DBUSER = client['users']
    user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    memberList = DBUSER.get_view_result('_design/fetch', 'byDesignation')['Gymkhana'][:]
    return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def student(request):
    DBUSER = client['users']
    user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    memberList = DBUSER.get_view_result('_design/fetch', 'byDesignation')['Student'][:]
    return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def admindashboard(request):
    if request.method == "GET":
        DBUSER = client['users']
        usernameView = DBUSER.get_view_result('_design/fetch', 'byUsername')
        user = usernameView[request.user.username]
        desigView = DBUSER.get_view_result('_design/fetch', 'byDesignation')
        userList = desigView['User'][:]
        if user[0]['value']['designation'] != 'admin':
            return redirect('/dashboard')
        x = usernameView[:]
        total = len(x)
        try:
            gymkhanaMem = desigView['Gymkhana'][:]
            studentMem = desigView['Student'][:]
            facultyMem = desigView['Faculty'][:]
        except Exception:
            return HttpResponse("""WIP""")
        gymkhana = len(gymkhanaMem)
        students = len(studentMem)
        faculty = len(facultyMem)
        return HttpResponse("""WIP""")

@login_required(redirect_field_name='nextPage', login_url='/login')
def comment(request, appId):
    DBCOMMENT = client['comments']
    DBAPPLICATIONS = client['applications']

    DBUSER = client['users']
    user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    picUrl = user[0]['value']['picUrl']
    dateCreated = str(datetime.datetime.strftime(datetime.datetime.now(), '%B %d, %Y, %H:%M %p'))
    DBACTIVITYLOG = client['activitylog']
    title = DBAPPLICATIONS[appId]['title']
    string = 'You commented on ' + title + '.'
    DBACTIVITYLOG.create_document({'string': string, 'type': 'comment',
                                   'username': request.user.username,
                                   'date': dateCreated})
    DBCOMMENT.create_document({'appId': appId, 'body': request.POST['body'],
                               'username': request.user.username, 'picUrl': picUrl,
                               'dateCreated': dateCreated})
    facultyList = DBAPPLICATIONS[appId]['facultyList']
    text = request.user.username + " commented on " + title
    for faculty in facultyList:
        if faculty is not request.user.username:           
            addNotification(text, faculty, "http://applicationrouting.eu-gb.mybluemix.net/applicationDetail/" + appId, "comment")
    if DBAPPLICATIONS[appId]['from'] is not request.user.username:
        addNotification(text, DBAPPLICATIONS[appId]['from'], "http://applicationrouting.eu-gb.mybluemix.net/applicationDetail/" + appId, "comment")
    return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def searchby(request):
    DBAPPLICATIONS = client['applications']
    DBACTIVITYLOG = client['activitylog']
    applications = DBAPPLICATIONS.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    query = ''
    query = request.GET.get("search")
    string = 'You searched ' + query + '.'
    date = str(datetime.datetime.strftime(datetime.datetime.now(), '%B %d, %Y, %H:%M %p'))
    DBACTIVITYLOG.create_document({'string': string, 'type': 'search',
                                   'username': request.user.username,
                                   'date': date})
    i = 0
    searchlist = []
    for application in applications:
        if re.search(query, application['value']['title'], re.IGNORECASE):
            searchlist.append(application)
            i += 1
    notificationList = getNotification(request.user.username)
    return HttpResponse("""WIP""")

@login_required(redirect_field_name='nextPage', login_url='/login')
def facultyAction(request, appId):
    DBAPPLICATIONS = client['applications']
    application = DBAPPLICATIONS[appId]
    if request.POST['submit'] == "Approved":
        facultyList = DBAPPLICATIONS[appId]['facultyList']
        text = request.user.username + " approved an application " + application['title']
        for faculty in facultyList:
            if faculty is not request.user.username:           
                addNotification(text, faculty, "http://applicationrouting.eu-gb.mybluemix.net/applicationDetail/" + appId, "approve")
        if DBAPPLICATIONS[appId]['from'] is not request.user.username:
            addNotification(text, DBAPPLICATIONS[appId]['from'], "http://applicationrouting.eu-gb.mybluemix.net/applicationDetail/" + appId, "approve")
        idx = application['facultyList'].index(application['nextBy'])
        if (idx + 1) != len(application['facultyList']):
            application['nextBy'] = application['facultyList'][idx + 1]
            text = request.user.username + " forwarded an application " + application['title']
            addNotification(text, application['nextBy'], "http://applicationrouting.eu-gb.mybluemix.net/applicationDetail/" + appId, "forward")
        else:
            application['status'] = request.POST['submit']
            application['nextBy'] = 'Its Over!!!'
    else:
        application['status'] = request.POST['submit']
        facultyList = DBAPPLICATIONS[appId]['facultyList']
        text = request.user.username + " disapproved an application " + application['title']
        for faculty in facultyList:
            if faculty is not request.user.username:           
                addNotification(text, faculty, "http://applicationrouting.eu-gb.mybluemix.net/applicationDetail/" + appId, "disapprove")
        if DBAPPLICATIONS[appId]['from'] is not request.user.username:
            addNotification(text, DBAPPLICATIONS[appId]['from'], "http://applicationrouting.eu-gb.mybluemix.net/applicationDetail/" + appId, "disapprove")
    
    application.save()
    return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def sentApplications(request):
    DBAPPLICATIONS = client['applications']
    DBUSER = client['users']
    DBACTIVITYLOG = client['activitylog']
    if request.method == "POST":
        if request.POST['submit'] == 'Delete':
            for appId in request.POST.getlist('applicationList'):
                doc = DBAPPLICATIONS[appId]
                title = doc['title']
                doc.delete()
                string = 'You deleted a sent application named ' + title + '.'
                date = str(datetime.datetime.strftime(datetime.datetime.now(), '%B %d, %Y, %H:%M %p'))
                DBACTIVITYLOG.create_document({'string': string, 'type': 'delete',
                                               'username': request.user.username,
                                               'date': date})
        return HttpResponse("""WIP""")
    applicationList = DBAPPLICATIONS.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    for application in applicationList:
        application['class'] = application['id']
        application['id'] = "#" + application['id']
    user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    notificationList = getNotification(request.user.username)
    return HttpResponse("""WIP""")

@login_required(redirect_field_name='nextPage', login_url='/login')
def deleteUser(request):
    DBUSERS = client['users']
    user = DBUSERS[request.POST['userId']]
    user.delete()
    return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def editDesignation(request):
    DBUSERS = client['users']
    user = DBUSERS[request.POST['userId']]
    facultyList = ['Director', 'Dean Academics', 'Dean Student Affair', 'Cultural Council Mentor',
                   'Sports Council Mentor', 'Sci. and Tech Council Mentor', 'Registrar']
    gymkhanaList = ['Student President', 'Cultural G.Sec.', 'Sports G.Sec.', 'Sci&Tech G.Sec.']
    if request.POST['designation'] in facultyList:
        user['designation'] = 'Faculty'
        user['post'] = request.POST['designation']
    elif request.POST['designation'] in gymkhanaList:
        user['designation'] = 'Gymkhana'
        user['post'] = request.POST['designation']
    else:
        user['designation'] = 'Student'
    user.save()
    text = "Admin assigned you designation " + user['designation']
    addNotification(text, user['username'], "http://applicationrouting.eu-gb.mybluemix.net/profile", "designation")
    return HttpResponse("""WIP""")


def addNotification(text, user, link, typeApp):
    DBNOTIFICATION = client['notifications']
    dateCreated = str(datetime.datetime.strftime(datetime.datetime.now(), '%B %d, %Y, %H:%M %p'))
    date = str(datetime.datetime.strftime(datetime.datetime.now(), '%d-%m-%Y, %H:%M %p'))
    DBNOTIFICATION.create_document({'text': text, 'to': user, 'dateCreated': dateCreated,
                                    'read': "false", 'link': link, 'type': typeApp, 'date': date})


def getNotification(username):
    DBNOTIFICATION = client['notifications']
    notificationlist = DBNOTIFICATION.get_view_result('_design/fetch', 'byDate')[:]
    notificationList = []
    for notification in notificationlist:
        val = notification['value']
        if val['to'] == username and val['read'] == "false":
            notificationList.append(notification)
    notificationList.reverse()
    return HttpResponse("""WIP""")


def read(request, notifyId):
    if request.method == "GET":
        DBNOTIFICATION = client['notifications']
        notification = DBNOTIFICATION[notifyId]
        notification['read'] = 'true'
        notification.save()
        return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def notifications(request):
    DBNOTIFICATION = client['notifications']
    notificationlist = DBNOTIFICATION.get_view_result('_design/fetch', 'byDate')
    notificationList = []
    for notification in notificationlist:
        if notification['value']['to'] == request.user.username and notification['value']['read'] == "false":
            notificationList.append(notification)
    notificationList.reverse()
    return HttpResponse("""WIP""")

def pdfPage(request, appId):
    DBAPPLICATIONS = client['applications']
    app = DBAPPLICATIONS[appId]
    DBUSERS = client['users']
    facultyList = []
    view = DBUSERS.get_view_result('_design/fetch', 'byUsername')
    for user in app['facultyList']:
        result = view[user]
        facultyList.append({'fullName': result[0]['value']['fullName'], 'post': result[0]['value']['post']})
    return HttpResponse("""WIP""")

@login_required(redirect_field_name='nextPage', login_url='/login')
def moveToTrash(request):
    DBACTIVITYLOG = client['activitylog']
    DBAPPLICATIONS = client['applications']
    DBTRASH = client['trash']
    for appId in request.POST.getlist('applicationList'):
        try:
            doc = DBAPPLICATIONS[appId]
        except Exception:
            continue
        title = doc['title']
        DBTRASH.create_document(doc)
        doc.delete()
        string = 'You deleted an application named ' + title + '.'
        date = str(datetime.datetime.strftime(datetime.datetime.now(), '%B %d, %Y, %H:%M %p'))
        DBACTIVITYLOG.create_document({'string': string, 'type': 'delete',
                                       'username': request.user.username,
                                       'date': date})
    return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def restore(request):
    DBAPPLICATIONS = client['applications']
    DBTRASH = client['trash']
    for appId in request.POST.getlist('applicationList'):
        try:
            doc = DBTRASH[appId]
        except Exception:
            continue
        DBAPPLICATIONS.create_document(doc)
        doc.delete()
    return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def deleteForever(request):
    DBTRASH = client['trash']
    for appId in request.POST.getlist('applicationList'):
        try:
            doc = DBTRASH[appId]
        except Exception:
            continue
        doc.delete()
    return HttpResponse("""WIP""")

@login_required(redirect_field_name='nextPage', login_url='/login')
def trash(request):
    DBTRASH = client['trash']
    DBUSER = client['users']
    applicationList = DBTRASH.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    applicationList1 = DBTRASH.get_view_result('_design/fetch', 'byUsername')[:]
    for app in applicationList1:
        if request.user.username in app['value']['facultyList']:
            applicationList.append(app)
    for application in applicationList:
        application['class'] = application['id']
        application['id'] = "#" + application['id']
    # applicationList = [application1, application2, application3]
    user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
    if user[0]['value']['designation'] == 'admin':
        return HttpResponse("""WIP""")
    notifcationList = getNotification(request.user.username)
    return HttpResponse("""WIP""")

@login_required(redirect_field_name='nextPage', login_url='/login')
def downloadPDF(request, appId):
    # create an API client instance
    pdf = weasyprint.HTML("http://applicationrouting.eu-gb.mybluemix.net/pdfPage/" + appId).write_pdf()
    response = HttpResponse(content_type="application/pdf")
    response["Cache-Control"] = "max-age=0"
    response["Accept-Ranges"] = "none"
    response["Content-Disposition"] = "attachment; filename=application.pdf"
    # send the generated PDF
    response.write(pdf)
    return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def adminProfile(request):
    if request.method == "GET":
        DBUSER = client['users']
        user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
        return HttpResponse("""WIP""")


@login_required(redirect_field_name='nextPage', login_url='/login')
def editAdminProfile(request):
    if request.method == "GET":
        DBUSER = client['users']
        user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
        return HttpResponse("""WIP""")
    else:
        # Saving in cloudant
        DBUSER = client['users']
        user = DBUSER.get_view_result('_design/fetch', 'byUsername')[request.user.username]
        user = DBUSER[user[0]['id']]
        user['collegeName'] = request.POST['collegename']
        user['password'] = request.POST['password']
        user['dob'] = request.POST['dob']
        user['gender'] = request.POST['gender']
        user['motto'] = request.POST['motto']
        user.save()
        return HttpResponse("""WIP""")
