// Product Filtering System
class ProductFilter {
    constructor() {
        this.productCards = document.querySelectorAll('.product-card');
        this.filterCheckboxes = document.querySelectorAll('.filter-checkbox');
        this.priceButtons = document.querySelectorAll('.price-btn');
        this.sortSelect = document.getElementById('sort-select');
        this.clearFiltersBtn = document.getElementById('clear-filters');
        this.applyFiltersBtn = document.getElementById('apply-filters');
        this.topSubcategories = document.getElementById('top-subcategories');
        this.brandSearch = document.getElementById('brand-search');
        this.loadMoreBtn = document.getElementById('load-more-btn');
        this.loadMoreContainer = document.getElementById('load-more-container');
        
        this.currentPage = 1;
        this.isLoading = false;
        
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // 상의 체크박스 변경 시 소분류 표시/숨김
        document.querySelectorAll('input[name="clothing_type"]').forEach(checkbox => {
            checkbox.addEventListener('change', this.handleClothingTypeChange.bind(this));
        });

        // 가격 버튼 클릭 이벤트
        this.priceButtons.forEach(button => {
            button.addEventListener('click', this.handlePriceButtonClick.bind(this));
        });

        // 필터 체크박스 이벤트
        this.filterCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', this.applyFilters.bind(this));
        });

        // 정렬 이벤트
        this.sortSelect.addEventListener('change', this.sortProducts.bind(this));
        
        // 버튼 이벤트
        this.clearFiltersBtn.addEventListener('click', this.clearAllFilters.bind(this));
        this.applyFiltersBtn.addEventListener('click', this.applyFilters.bind(this));

        // 브랜드 검색 실시간 필터링
        this.brandSearch.addEventListener('input', this.applyFilters.bind(this));

        // 가격 입력 필드 변경 시 필터링
        document.getElementById('min-price').addEventListener('input', this.applyFilters.bind(this));
        document.getElementById('max-price').addEventListener('input', this.applyFilters.bind(this));

        // Load More 이벤트
        this.loadMoreBtn.addEventListener('click', this.loadMoreProducts.bind(this));
    }

    handleClothingTypeChange(event) {
        if (event.target.value === 'top' && event.target.checked) {
            this.topSubcategories.style.display = 'block';
        } else if (event.target.value === 'top' && !event.target.checked) {
            this.topSubcategories.style.display = 'none';
            // 상의 소분류 체크박스들 해제
            document.querySelectorAll('input[name="top_subcategory"]').forEach(cb => cb.checked = false);
        }
    }

    handlePriceButtonClick(event) {
        const minPrice = event.target.dataset.min;
        const maxPrice = event.target.dataset.max;
        document.getElementById('min-price').value = minPrice;
        document.getElementById('max-price').value = maxPrice;
    }

    applyFilters() {
        const selectedGenders = Array.from(document.querySelectorAll('input[name="gender"]:checked')).map(cb => cb.value);
        const selectedTypes = Array.from(document.querySelectorAll('input[name="clothing_type"]:checked')).map(cb => cb.value);
        const selectedSubcategories = Array.from(document.querySelectorAll('input[name="top_subcategory"]:checked')).map(cb => cb.value);
        const selectedRatings = Array.from(document.querySelectorAll('input[name="rating"]:checked')).map(cb => cb.value);
        const minPrice = document.getElementById('min-price').value;
        const maxPrice = document.getElementById('max-price').value;
        const brandSearchTerm = this.brandSearch.value.toLowerCase();

        let visibleCount = 0;

        this.productCards.forEach(card => {
            let shouldShow = true;

            // 성별 필터
            if (selectedGenders.length > 0) {
                const cardGender = card.dataset.gender.toLowerCase();
                if (!selectedGenders.some(gender => cardGender.includes(gender))) {
                    shouldShow = false;
                }
            }

            // 의류 타입 필터
            if (selectedTypes.length > 0) {
                const cardType = card.dataset.type.toLowerCase();
                if (!selectedTypes.some(type => cardType.includes(type))) {
                    shouldShow = false;
                }
            }

            // 상의 소분류 필터
            if (selectedSubcategories.length > 0) {
                const cardSubcategory = card.dataset.subcategory.toLowerCase();
                if (!selectedSubcategories.some(sub => cardSubcategory.includes(sub))) {
                    shouldShow = false;
                }
            }

            // 가격 필터
            if (minPrice || maxPrice) {
                const cardPrice = parseInt(card.dataset.price);
                if (minPrice && cardPrice < parseInt(minPrice)) shouldShow = false;
                if (maxPrice && cardPrice > parseInt(maxPrice)) shouldShow = false;
            }

                                // 평점 필터
                    if (selectedRatings.length > 0) {
                        const cardRating = parseFloat(card.dataset.rating);
                        const hasMatchingRating = selectedRatings.some(rating => {
                            const minRating = parseFloat(rating);
                            return cardRating >= minRating;
                        });
                        if (!hasMatchingRating) {
                            shouldShow = false;
                        }
                    }

            // 브랜드 검색
            if (brandSearchTerm) {
                const cardBrand = card.dataset.brand.toLowerCase();
                if (!cardBrand.includes(brandSearchTerm)) {
                    shouldShow = false;
                }
            }

            card.style.display = shouldShow ? 'block' : 'none';
            if (shouldShow) visibleCount++;
        });

        // 결과가 없을 때 메시지 표시
        const noResults = document.getElementById('no-results');
        if (visibleCount === 0) {
            noResults.style.display = 'block';
        } else {
            noResults.style.display = 'none';
        }

        this.updateActiveFilters();
        this.showLoadMoreButton();
    }

    updateActiveFilters() {
        const activeFiltersContainer = document.getElementById('active-filters');
        const activeFilters = [];

        // 선택된 필터들 수집
        document.querySelectorAll('.filter-checkbox:checked').forEach(cb => {
            activeFilters.push(cb.parentElement.textContent.trim());
        });

        const minPrice = document.getElementById('min-price').value;
        const maxPrice = document.getElementById('max-price').value;
        if (minPrice || maxPrice) {
            activeFilters.push(`가격: ${minPrice || '0'}원 ~ ${maxPrice || '∞'}원`);
        }

        if (this.brandSearch.value) {
            activeFilters.push(`브랜드: ${this.brandSearch.value}`);
        }

        // 활성 필터 표시
        if (activeFilters.length > 0) {
            activeFiltersContainer.innerHTML = `
                <div class="active-filter-tags">
                    ${activeFilters.map(filter => `
                        <span class="filter-tag">${filter}</span>
                    `).join('')}
                </div>
            `;
        } else {
            activeFiltersContainer.innerHTML = '';
        }
    }

    clearAllFilters() {
        document.querySelectorAll('.filter-checkbox').forEach(cb => cb.checked = false);
        document.getElementById('min-price').value = '';
        document.getElementById('max-price').value = '';
        this.brandSearch.value = '';
        this.topSubcategories.style.display = 'none';
        this.sortSelect.value = 'default';
        
        // 모든 상품 카드 표시
        this.productCards.forEach(card => card.style.display = 'block');
        document.getElementById('no-results').style.display = 'none';
        this.updateActiveFilters();
    }

    sortProducts() {
        const sortValue = this.sortSelect.value;
        const productGrid = document.getElementById('product-grid');
        const cards = Array.from(productGrid.children);

        cards.sort((a, b) => {
            switch(sortValue) {
                case 'price-low':
                    const priceA = parseInt(a.dataset.price);
                    const priceB = parseInt(b.dataset.price);
                    return priceA - priceB;
                case 'price-high':
                    const priceA2 = parseInt(a.dataset.price);
                    const priceB2 = parseInt(b.dataset.price);
                    return priceB2 - priceA2;
                case 'rating':
                    const ratingA = parseFloat(a.dataset.rating);
                    const ratingB = parseFloat(b.dataset.rating);
                    return ratingB - ratingA;
                case 'name':
                    const nameA = a.querySelector('h3').textContent;
                    const nameB = b.querySelector('h3').textContent;
                    return nameA.localeCompare(nameB);
                default:
                    return 0;
            }
        });

        cards.forEach(card => productGrid.appendChild(card));
    }

    async loadMoreProducts() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.loadMoreBtn.textContent = '로딩 중...';
        
        try {
            // 현재 필터 상태를 URL 파라미터로 변환
            const params = new URLSearchParams();
            params.append('page', this.currentPage + 1);
            params.append('limit', 10);
            
            const selectedGenders = Array.from(document.querySelectorAll('input[name="gender"]:checked')).map(cb => cb.value);
            if (selectedGenders.length > 0) {
                params.append('gender', selectedGenders[0]);
            }
            
            const selectedTypes = Array.from(document.querySelectorAll('input[name="clothing_type"]:checked')).map(cb => cb.value);
            if (selectedTypes.length > 0) {
                params.append('clothing_type', selectedTypes[0]);
            }
            
            const selectedSubcategories = Array.from(document.querySelectorAll('input[name="top_subcategory"]:checked')).map(cb => cb.value);
            if (selectedSubcategories.length > 0) {
                params.append('subcategory', selectedSubcategories[0]);
            }
            
            const minPrice = document.getElementById('min-price').value;
            const maxPrice = document.getElementById('max-price').value;
            if (minPrice) params.append('min_price', minPrice);
            if (maxPrice) params.append('max_price', maxPrice);
            
            const selectedRatings = Array.from(document.querySelectorAll('input[name="rating"]:checked')).map(cb => cb.value);
            if (selectedRatings.length > 0) {
                params.append('min_rating', selectedRatings[0]);
            }
            
            const brandSearchTerm = this.brandSearch.value;
            if (brandSearchTerm) {
                params.append('brand', brandSearchTerm);
            }
            
            const response = await fetch(`/api/products?${params.toString()}`);
            const data = await response.json();
            
            if (data.products && data.products.length > 0) {
                // 새로운 상품들을 그리드에 추가
                data.products.forEach(product => {
                    const productCard = this.createProductCard(product);
                    document.getElementById('product-grid').appendChild(productCard);
                });
                
                this.currentPage++;
                
                // 더 로드할 상품이 없으면 버튼 숨김
                if (!data.has_more) {
                    this.loadMoreContainer.style.display = 'none';
                }
            }
        } catch (error) {
            console.error('Error loading more products:', error);
        } finally {
            this.isLoading = false;
            this.loadMoreBtn.textContent = '더 많은 상품 보기';
        }
    }

    createProductCard(product) {
        const card = document.createElement('div');
        card.className = 'product-card';
        card.dataset.gender = product.성별 || '';
        card.dataset.type = product.의류타입 || '';
        card.dataset.subcategory = product.소분류 || '';
        card.dataset.price = product.processed_price || '0';
        card.dataset.rating = product.평점 || '0';
        card.dataset.brand = product.브랜드 || '';
        
        // 평점에 따른 별표 생성
        const rating = parseFloat(product.평점 || 0);
        let stars = '';
        for (let i = 0; i < 5; i++) {
            if (rating >= i + 1) {
                stars += '⭐';
            } else if (rating >= i + 0.5) {
                stars += '☆';
            } else {
                stars += '☆';
            }
        }
        
        card.innerHTML = `
            <img src="${product.대표이미지URL}" alt="${product.상품명}">
            <h3>${product.상품명}</h3>
            <p class="brand">${product.브랜드 || ''}</p>
            <p class="price">${product.가격}</p>
            <div class="rating">
                <span class="stars" data-rating="${product.평점 || '0'}">${stars}</span>
                <span class="rating-text">${product.평점 || '0'}/5</span>
            </div>
            <button class="add-to-cart">장바구니에 추가</button>
        `;
        
        return card;
    }

    showLoadMoreButton() {
        this.loadMoreContainer.style.display = 'block';
        this.currentPage = 1;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.productFilter = new ProductFilter();
    window.clearAllFilters = () => window.productFilter.clearAllFilters();
}); 