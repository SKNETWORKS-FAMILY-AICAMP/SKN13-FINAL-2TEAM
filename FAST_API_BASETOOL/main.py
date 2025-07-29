from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Corrected imports
from apps.home.router import router as home_router
from apps.auth.router import router as auth_router
from apps.recommend.router import router as recommend_router
from apps.review.router import router as review_router
from apps.cart.router import router as cart_router
from apps.products.router import router as products_router
from apps.survey.router import router as survey_router
from apps.faq.router import router as faq_router

app = FastAPI()

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
# Note: The home router does not have a prefix, so it handles the root path "/".
app.include_router(home_router, tags=["Home"])

# For other routers, the prefix is added. 
# e.g., the /login path in auth/router.py becomes /auth/login
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(recommend_router, prefix="/recommend", tags=["Recommendation"])
app.include_router(review_router, prefix="/review", tags=["Review"])
app.include_router(cart_router, prefix="/cart", tags=["Cart"])
app.include_router(products_router, prefix="/products", tags=["Products"])
app.include_router(survey_router, prefix="/survey", tags=["Survey"])
app.include_router(faq_router, prefix="/faq", tags=["FAQ"])
