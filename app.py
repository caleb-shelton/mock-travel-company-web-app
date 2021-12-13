from __future__ import print_function
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from flask import Flask, render_template, request, redirect, flash, url_for
from flask_wtf import FlaskForm
from flask_mail import Mail, Message
from wtforms.validators import InputRequired
from wtforms import StringField, SubmitField, PasswordField, BooleanField, SelectField, RadioField
from wtforms.fields import TextAreaField
from wtforms.fields.html5 import DateField
from wtforms.validators import InputRequired, Email, Length
from datetime import datetime, timedelta
import datetime
import time
import requests
import csv

app = Flask(__name__)

DAYS_IN_A_YEAR = 365

rateForMonth = {
    "January": 750,
    "February": 750,
    "March": 950,
    "April": 950,
    "May": 950,
    "June": 1200,
    "July": 1200,
    "August": 1200,
    "September": 750,
    "October": 750,
    "November": 750,
    "December": 1200
  }

SCOPES = 'https://www.googleapis.com/auth/calendar'

# We can encrypt mail password using
# os.environ['MAIL_PASSWORD']
# and set the os environment in cmd using
# set MAIL_PASSWORD="{your_mail_password}"
# not implemented to reduce any risks of features not working in lab demo.

# This is for Cross-Site Request Forgery (CSRF) protection.
app.config['SECRET_KEY'] = ''

# This configures the email settings and login information.
app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 1
app.config['MAIL_USERNAME'] = ''
app.config['MAIL_PASSWORD'] = ''
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)

def getStartEndDate(bookingData):
    startDate = datetime.datetime.strptime(bookingData[3], "%d/%m/%Y")
    endDate = datetime.datetime.strptime(bookingData[4], "%d/%m/%Y")
    return startDate, endDate

# Requests data from "https://openweathermap.org/current", this request returns a
# JSON object containing weather data. I selected to extract the temperature,
# windspeed and a description of the current weather.
def getWeatherData():
    weatherReq = requests.get('')
    weather_object = weatherReq.json()
    temp_kelvins = float(weather_object['main']['temp'])
    temp_celcius = (str(round(temp_kelvins - 273.15)) + "°")
    weather = weather_object['weather']
    windspeed = str(weather_object['wind']['speed'])

    # Cycles through the nested dictionary to retrieve weather information as there
    # is a nested array within the object.
    for item in weather_object['weather']:
        weatherDes = item['description']

    weatherData= [temp_celcius, windspeed, weatherDes]
    return weatherData

# When a valid start and end date is inputted and confirmed by the user on
# the confirm rent page, this will be added to our Google account's calendar
# which is then displayed on the website. So this code adds the booking to the
# calendar.

# I learnt about how to use the Google Calendar API through their official docs
# which contained sample code that I have used belowself.
# reference: https://developers.google.com/calendar/quickstart/python
# and https://developers.google.com/calendar/create-events
def addBookingToCalendar(bookingData):
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    store = file.Storage('token.json')
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
        creds = tools.run_flow(flow, store)
    service = build('calendar', 'v3', http=creds.authorize(Http()))

    startDate, endDate = getStartEndDate(bookingData)

    # Increment end date by 1 as google calendar didn't display end date as
    # booked. We display the end date as booked to allow for cleaning append
    # preperation of the house for the next day. So the customer can arrive
    # before noon and leave after noon on their end date.
    endDate += datetime.timedelta(days=1)

    # Format the datetime values according to RFC3339
    # https://tools.ietf.org/html/rfc3339
    startDate = str(startDate.isoformat('T'))
    endDate = str(endDate.isoformat('T'))

    event = {
      'summary': 'Booking',
      'location': 'Holywood, Los Angeles, California',
      'description': 'A booking from a customer',
      'start': {
        'dateTime': startDate,
        'timeZone': 'Europe/Belfast',
      },
      'end': {
        'dateTime': endDate,
        'timeZone': 'Europe/Belfast',
      }
    }

    # Insert the event I created into our google calendar. I am using the
    # 'primary' keyword to access the primary calendar on my Google account
    # I have linked it to.
    event = service.events().insert(calendarId='primary', body=event).execute()
    print('Event created: %s' % (event.get('htmlLink')))

# This code gets the current month and checks the booking rate for that
# particular month against the rateForMonth dictionary.
def getCostPerNight():
    # Although rateForMonth is constant, it is only required upon calculating
    # a booking price. Therefore, we have defined it locally to be more memory
    # efficient.
    # rateForMonth contains the price per night in GBP for a particular month.
    rateForMonth = {
        "January": 750,
        "February": 750,
        "March": 950,
        "April": 950,
        "May": 950,
        "June": 1200,
        "July": 1200,
        "August": 1200,
        "September": 750,
        "October": 750,
        "November": 750,
        "December": 1200
      }
    currentMonth = datetime.datetime.now().strftime("%B")
    return rateForMonth[currentMonth]

# This module of code gets the number of booking per month.
# It does this by cycling through the code using for loop and adds one to the
# corresponding month and then saves it to a dictionary.
# This data is then used later on to create the bar chart.
def getBookingsAMonth():
    bookingsAMonthDict = {  "January": 0,
                            "February": 0,
                            "March": 0,
                            "April": 0,
                            "May": 0,
                            "June": 0,
                            "July": 0,
                            "August": 0,
                            "September": 0,
                            "October": 0,
                            "November": 0,
                            "December": 0 }
    bookingData = readFile('static\\bookings.csv')
    for item in bookingData:
        startDate, _ = getStartEndDate(item)
        startDate = startDate.date()
        bookingsAMonthDict[startDate.strftime("%B")] += 1
    return bookingsAMonthDict

# This function wipes the file of any data.
def wipeFile(filePath):
    f = open(filePath, "w+")
    f.close()

# This returns the number of days that are booked for the current year.
# The program reads in the all of the bookings from the CSV file and goes through
# each one checking to see if the date matches the one of the current year.
# If it does the number of booked days increases equal to the length of the booking.
# This date is then used to create the Pie chart displayed in the admin panel.
def getBookedDays():
    bookedDays = 0

    bookingData = readFile('static\\bookings.csv')
    for item in bookingData:
        startDate, endDate = getStartEndDate(item)
        startDate = startDate.date()
        endDate = endDate.date()
        if startDate.year == datetime.datetime.now().year:
            tempDate = endDate - startDate
            bookedDays += tempDate.days
    return bookedDays

# The "getDays" function reads the specified file selected by the filePath
# it returns the total days from all of the booked dates in the csv.
def getDays(filePath):
    bookingData = readFile(filePath)
    totalDays = 0
    for item in bookingData:
        startDate, endDate = getStartEndDate(item)
        startDate = startDate.date()
        endDate = endDate.date()
        tempDate = endDate - startDate
        totalDays += tempDate.days
    return totalDays

# This function returns todays date using the datetime objects method "now".
# This combined with the "date()" function gets the current date.
def getTodaysDate():
    dateNow = datetime.datetime.now().date()
    dateTodayString = datetime.datetime.strptime(str(dateNow),'%Y-%m-%d').strftime('%d/%m/%Y')
    dateToday = time.strptime(dateTodayString, "%d/%m/%Y")
    return dateToday

# To get the average review I read in the csv file containing the reviews. For every
# review it adds one each time to the total reviews, and at the same time add up each
# of the scores. This is then used to calcualte the average score.
def getAverageReview():
    averageScore = 0
    reviewCount = 0
    totalScore = 0
    reviewData = readFile('static\\reviews.csv')

    for review in reviewData:
        totalScore += int(review[1])
        reviewCount += 1

    if reviewCount == 0:
        averageScore = 0
    else:
        averageScore = round((totalScore/reviewCount), 1)
    return averageScore

# We have decided that a most valued customer is a customer who has booked
# atleast twice with us. To make a list of most valued mvCustomersList
# we iterate through all the booking data and identify a customer by their email
# (as you might have customers with the same name so email is our primary key)
# We then make a dictionary of all the emails and how many times they appear in
# bookingData. We then iterate through the dictionary and where the value is
# > 1 we append the first name of the customer to the list.
def getMvCustomerData():
    found = False
    customers = {}
    mvCustomersList = []
    days = 0
    bookingData = readFile('static\\bookings.csv')
    for item in bookingData:
        if not item[2] in customers:
            customers[item[2]] = 1
        else:
            customers[item[2]] += 1
    for key, value in customers.items():
        if value > 1:
            for item in bookingData:
                if item[2] == key:
                    customerName = str(item[0]+" "+item[1])
                    break
            for item in bookingData:
                if item[2] == key:
                     startDate, endDate = getStartEndDate(item)
                     startDate = startDate.date()
                     endDate = endDate.date()
                     tempDate = endDate - startDate
                     days += tempDate.days
            mvCustomersList.append([customerName, value, days])
            days = 0

    return mvCustomersList

# This was added because the choices variable in ConfirmBookings wasn't updating
# This returns a list of tuples in the form (uniquekey, customername)
# The unique key (which we have used as the startDate of the booking)
# is required by the form SelectField in ConfirmBookings.
def readFileTuples():
    bookingTuples = []
    bookings = readFile('static\\bookings.csv')
    for item in bookings:
        bookingTuples.append(tuple([str(item[3]), str(item[0]+" "+item[1])]))
    return bookingTuples

# Reads a csv file with given file path.
def readFile(filePath):
    with open(filePath, 'r') as inFile:
        reader = csv.reader(inFile)
        aList = [row for row in reader]
        return aList

# Overwrites csv file with given file path and new list data.
def writeFile(filePath, theList):
    with open(filePath, 'w', newline='') as outFile:
        writer = csv.writer(outFile)
        writer.writerows(theList)

class RentForm(FlaskForm):
    firstName = StringField('First name:', validators=[InputRequired()])
    lastName = StringField('Last name:', validators=[InputRequired()])
    email = StringField('Email:', validators=[InputRequired(), Email(message='Invalid email')])
    # Format is kept in Y/m/d because it was causing errors changing it, such
    # as not displaying the date/calendar picker in the browser so we kept it in
    # this format and modified the format in code further down.
    startDate = DateField('Start date of rent:', format='%Y-%m-%d', validators=[InputRequired('')])
    endDate = DateField('End date of rent:', format='%Y-%m-%d', validators=[InputRequired('')])
    submit = SubmitField('Book')

# Flask WTForms for providing forms and validation where we use forms in the
# website
class AdminForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Login')

class ConfirmBookings(FlaskForm):
    bookingTuples = readFileTuples()
    bookees = SelectField('Bookee Name:', choices = bookingTuples, validators = [InputRequired()])
    confirm = SubmitField('Confirm Booking')

class ReviewForm(FlaskForm):
    name = StringField('Name:', validators=[InputRequired()])
    score = RadioField('Score:', choices = [('0', 0), ('1', 1), ('3', 3), ('4', 4), ('5', 5)], validators = [InputRequired()])
    comment = TextAreaField('Comment:', validators=[InputRequired()])
    submit = SubmitField('Post Review')

# Page routing
@app.route("/", methods=['GET', 'POST'])
@app.route("/index", methods=['GET', 'POST'])
def index():
    form = ReviewForm()

    reviews = readFile('static\\reviews.csv')

    if form.validate_on_submit():
        name = form.name.data
        score = form.score.data
        comment = form.comment.data
        dateNow = datetime.datetime.now().date()
        dateFormatted = datetime.datetime.strptime(str(dateNow), '%Y-%m-%d').strftime('%d/%m/%Y')
        reviews.append([name, score, comment, dateFormatted])
        writeFile('static\\reviews.csv', reviews)
        return redirect(url_for('index'))
    return render_template('index.html', form=form, reviews=reviews)

@app.route('/attractions')
def attractions():
    return render_template('attractions.html')

@app.route('/rent', methods=['GET', 'POST'])
def rent():
    form = RentForm()
    bookingData = readFile('static\\bookings.csv')

    weatherData = getWeatherData()

    if form.validate_on_submit():
        bookingInfo = readFile('static\\bookings.csv')
        startDate = datetime.datetime.strptime(str(form.startDate.data), '%Y-%m-%d').strftime('%d/%m/%Y') #make it in the right date format
        endDate = datetime.datetime.strptime(str(form.endDate.data), '%Y-%m-%d').strftime('%d/%m/%Y')
        startDateComparing = time.strptime(startDate, "%d/%m/%Y")
        endDateComparing = time.strptime(endDate, "%d/%m/%Y")
        data = [form.firstName.data, form.lastName.data, form.email.data, startDate, endDate, 'no']

        failed = False
        for item in bookingInfo:
            startDateExisting = time.strptime(item[3], "%d/%m/%Y")
            endDateExisting = time.strptime(item[4], "%d/%m/%Y")
            # The logic below is for the booking validation, ensuring none of
            # the bookings: overlap, book before the present, book on the same
            # day (as we decided to base it on nights so there has to be a
            # minimum of one night) and making sure the end date is not before
            # the start date.
            if (startDateComparing >= startDateExisting and startDateComparing <= endDateExisting) or (endDateComparing >= startDateExisting and endDateComparing <= endDateExisting) or (startDateComparing <= startDateExisting and endDateComparing >= endDateExisting):
                failed = True
                return redirect(url_for('failed'))# Custom error pages give the user a better idea of whats going wrong.
            elif  startDateComparing < getTodaysDate():
                failed = True
                return redirect(url_for('failed2'))
            elif startDateComparing == endDateComparing:
                failed = True
                return redirect(url_for('failed3'))
            elif endDateComparing < startDateComparing:
                failed = True
                return redirect(url_for('failed4'))

        if not failed:
            bookingInfo.append(data)
            wipeFile('static\\tempbookings.csv')
            data2 = []
            data2.append(data)
            writeFile('static\\tempbookings.csv', data2)
            return redirect(url_for('confirmbooking'))
    return render_template('rent.html', form=form, bookingData=bookingData, weatherData=weatherData)

@app.route('/adminlogin', methods=['GET', 'POST'])# This takes you to the login page for the admin
def adminlogin():
    form = AdminForm()
    if form.validate_on_submit():
        if form.username.data == 'admin' and form.password.data == 'password':
            return redirect(url_for('adminpanel'))
        else:
            return redirect(url_for('loginfail'))
    return render_template('adminlogin.html', form=form)

# Routes the user to the admin panel
# Makes calls to various functions to collect useful data to be displayed
# graphically on page.
@app.route('/adminpanel', methods=['GET', 'POST'])
def adminpanel():
    revenue = getDays('static\\bookings.csv') * getCostPerNight() # Gets the total revenue
    form = ConfirmBookings()

    bookingsAMonth = []

    bookingsAMonthTemp = getBookingsAMonth()
    for key, value in bookingsAMonthTemp.items():
        bookingsAMonth.append(value)

    revenueAMonthTemp = bookingsAMonth
    revenueAMonth = []

    for item in revenueAMonthTemp:
        revenueAMonth.append(item*getCostPerNight())

    numBookedDays = getBookedDays()
    numUnbookedDays = (DAYS_IN_A_YEAR - numBookedDays)

    averageReview = getAverageReview()

    mvCustomerList = getMvCustomerData()
    form.bookees.choices = readFileTuples()
    bookingData = readFile('static\\bookings.csv')
    if form.validate_on_submit():
        name = form.bookees.data
        bookings = readFile('static\\bookings.csv')
        for item in bookings:
            if str(item[3]) == name:
                item[5] = 'yes'
        writeFile('static\\bookings.csv', bookings)
        return redirect(url_for('adminpanel'))

    return render_template('adminpanel.html', form=form, bookingData=bookingData,
    mvCustomerList=mvCustomerList, revenue=revenue, bookingsAMonth=bookingsAMonth,
    numBookedDays=numBookedDays,numUnbookedDays=numUnbookedDays, revenueAMonth=revenueAMonth,
    averageReview=averageReview)

# This is the step that adds a users booking to the calendar and moves their booking
# data from the temporary csv to the main booking csv.
@app.route('/confirmed', methods=['GET', 'POST'])
def confirmed():
    bookingData = readFile('static\\tempbookings.csv')
    bookingDataExisting = readFile('static\\bookings.csv')
    bookingDataExisting.append(bookingData[0])
    tempBookingData = bookingData[0]
    writeFile('static\\bookings.csv', bookingDataExisting)

    # Defines email content and sends it to ther customer
    msg = Message('Thank you for your booking', sender = ('S&S Booking Team','test@gmail.com'), recipients = [tempBookingData[2]])
    msg.body = "Hello " + tempBookingData[0] + ", \n\nThanks for confirming your booking between these two dates: " + str(tempBookingData[3]) + ", to " + str(tempBookingData[4]) + "\n\nBest wishes,\n\nS&S Booking Team"
    mail.send(msg)

    # Add the customers booking to google calender
    addBookingToCalendar(bookingData[0])

    return render_template('confirmed.html')

# This displays the cost of the stay to the user giving them all the information before they go ahead and confirm
# their booking or choose to stop the process.
@app.route('/confirmbooking', methods=['GET', 'POST'])
def confirmbooking():
    bookingData = readFile('static\\tempbookings.csv')
    bookingData = bookingData[-1]
    firstName = bookingData[0]
    lastName = bookingData[1]
    email = bookingData[2]
    startDate = bookingData[3]
    endDate = bookingData[4]
    confirmed = bookingData[5]
    daysBooked = getDays('static\\tempbookings.csv')
    costPerNight = getCostPerNight()
    priceOfStay = daysBooked * costPerNight
    return render_template('confirmbooking.html', firstName=firstName, lastName=lastName, email=email,
    startDate=startDate, endDate=endDate, confirmed=confirmed, daysBooked=daysBooked, costPerNight=costPerNight, priceOfStay=priceOfStay)

# Routing for all of the error pages.
@app.route('/failed')
def failed():
    return render_template('failed.html')

@app.route('/failed2')
def failed2():
    return render_template('failed2.html')

@app.route('/failed3')
def failed3():
    return render_template('failed3.html')

@app.route('/failed4')
def failed4():
    return render_template('failed4.html')

@app.route('/loginfail')
def loginfail():
    return render_template('loginfail.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__': # Makes flask refresh if the app.py is modified.
    app.run(debug=True)
