from django.shortcuts import render

def review_list_view(request):
    return render(request, 'review/review_list.html')