from django.shortcuts import render

def recommendation_home(request):
    return render(request, 'recommendation/home.html')