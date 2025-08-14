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
        // 의류 타입 체크박스 변경 시 소분류 표시/숨김
        document.querySelectorAll('input[name="clothing_type"]').forEach(checkbox => {
            checkbox.addEventListener('change', this.handleClothingTypeChange.bind(this));
        });

        // 가격 버튼 클릭 이벤트
        this.priceButtons.forEach(button => {
            button.addEventListener('click', this.handlePriceButtonClick.bind(this));
        });

        // 평점 버튼 클릭 이벤트
        document.querySelectorAll('.rating-btn').forEach(button => {
            button.addEventListener('click', this.handleRatingButtonClick.bind(this));
        });

        // 필터들은 이제 '필터 적용' 버튼으로 수동 제어됩니다.
        this.filterCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => this.updateFilterConstraints());
        });

        // 정렬 이벤트
        this.sortSelect.addEventListener('change', this.sortProducts.bind(this));
        
        // 버튼 이벤트
        this.clearFiltersBtn.addEventListener('click', this.clearAllFilters.bind(this));
        this.applyFiltersBtn.addEventListener('click', this.applyFilters.bind(this));

        // Load More 이벤트
        this.loadMoreBtn.addEventListener('click', this.loadMoreProducts.bind(this));

        this.updateFilterConstraints(); // Initial check
    }

    updateFilterConstraints() {
        const maleCheckbox = document.querySelector('input[name="gender"][value="male"]');
        const skirtCheckbox = document.querySelector('input[name="clothing_type"][value="skirt"]');

        const skirtOption = skirtCheckbox.closest('.filter-option');
        const maleOption = maleCheckbox.closest('.filter-option');

        // 남성이 선택되면 스커트 비활성화
        if (maleCheckbox.checked) {
            skirtCheckbox.disabled = true;
            skirtOption.classList.add('disabled');
        } else {
            skirtCheckbox.disabled = false;
            skirtOption.classList.remove('disabled');
        }

        // 스커트가 선택되면 남성 비활성화
        if (skirtCheckbox.checked) {
            maleCheckbox.disabled = true;
            maleOption.classList.add('disabled');
        } else {
            maleCheckbox.disabled = false;
            maleOption.classList.remove('disabled');
        }
    }

    handleClothingTypeChange(event) {
        const isChecked = event.target.checked;
        const value = event.target.value;
        
        // 현재 선택된 의류 타입들 확인
        const selectedTypes = Array.from(document.querySelectorAll('input[name="clothing_type"]:checked')).map(cb => cb.value);
        
        // 모든 소분류 숨기기
        this.topSubcategories.style.display = 'none';
        document.getElementById('bottom-subcategories').style.display = 'none';
        document.getElementById('skirt-subcategories').style.display = 'none';
        
        // 선택된 의류 타입에 따라 해당하는 소분류들 표시
        selectedTypes.forEach(type => {
            switch(type) {
                case 'top':
                    this.topSubcategories.style.display = 'block';
                    break;
                case 'bottom':
                    document.getElementById('bottom-subcategories').style.display = 'block';
                    break;
                case 'skirt':
                    document.getElementById('skirt-subcategories').style.display = 'block';
                    break;
            }
        });
        
        // 체크 해제 시 해당 소분류 체크박스들도 해제
        if (!isChecked) {
            switch(value) {
                case 'top':
                    document.querySelectorAll('input[name="top_subcategory"]').forEach(cb => cb.checked = false);
                    break;
                case 'bottom':
                    document.querySelectorAll('input[name="bottom_subcategory"]').forEach(cb => cb.checked = false);
                    break;
                case 'skirt':
                    document.querySelectorAll('input[name="skirt_subcategory"]').forEach(cb => cb.checked = false);
                    break;
            }
        }
    }

    handlePriceButtonClick(event) {
        const minPrice = event.target.dataset.min;
        const maxPrice = event.target.dataset.max;
        document.getElementById('min-price').value = minPrice;
        document.getElementById('max-price').value = maxPrice;
        // this.applyFilters(); // '필터 적용' 버튼으로 수동 적용
    }

    handleRatingButtonClick(event) {
        const minRating = event.target.dataset.min;
        const maxRating = event.target.dataset.max;
        document.getElementById('min-rating').value = minRating;
        document.getElementById('max-rating').value = maxRating;
        // this.applyFilters(); // '필터 적용' 버튼으로 수동 적용
    }

    applyFilters() {
        const selectedGenders = Array.from(document.querySelectorAll('input[name="gender"]:checked')).map(cb => cb.value);
        const selectedTypes = Array.from(document.querySelectorAll('input[name="clothing_type"]:checked')).map(cb => cb.value);
        const selectedSubcategories = Array.from(document.querySelectorAll('input[name="top_subcategory"]:checked')).map(cb => cb.value);
        const minPrice = document.getElementById('min-price').value;
        const maxPrice = document.getElementById('max-price').value;
        const minRating = document.getElementById('min-rating').value;
        const maxRating = document.getElementById('max-rating').value;
        const brandSearchTerm = this.brandSearch.value.trim();
        const selectedBrands = brandSearchTerm ? brandSearchTerm.split(',').map(brand => brand.trim()).filter(brand => brand.length > 0) : [];

        let visibleCount = 0;

        this.productCards.forEach(card => {
            let shouldShow = true;

            // 성별 필터 (키 매칭 강화: gender_key 존재 시 우선)
            if (selectedGenders.length > 0) {
                const cardGenderKey = (card.dataset.genderKey || card.dataset.gender || '').toLowerCase();
                if (!selectedGenders.some(gender => cardGenderKey === gender.toLowerCase())) {
                    shouldShow = false;
                }
            }

            // 소분류 필터 (소분류가 선택되면 의류 타입 필터는 무시)
            const selectedTopSubcategories = Array.from(document.querySelectorAll('input[name="top_subcategory"]:checked')).map(cb => cb.value);
            const selectedBottomSubcategories = Array.from(document.querySelectorAll('input[name="bottom_subcategory"]:checked')).map(cb => cb.value);
            const selectedSkirtSubcategories = Array.from(document.querySelectorAll('input[name="skirt_subcategory"]:checked')).map(cb => cb.value);
            
            const allSelectedSubcategories = [...selectedTopSubcategories, ...selectedBottomSubcategories, ...selectedSkirtSubcategories];
            
            if (allSelectedSubcategories.length > 0) {
                // 소분류가 선택된 경우, 소분류로만 필터링
                const cardSubcategoryKey = (card.dataset.subcatKey || card.dataset.subcategory || '').toLowerCase();
                if (!allSelectedSubcategories.some(sub => cardSubcategoryKey === sub.toLowerCase())) {
                    shouldShow = false;
                }
            } else {
                // 소분류가 선택되지 않은 경우에만 의류 타입 필터 적용
                if (selectedTypes.length > 0) {
                    const cardTypeKey = (card.dataset.typeKey || card.dataset.type || '').toLowerCase();
                    if (!selectedTypes.some(type => cardTypeKey === type.toLowerCase())) {
                        shouldShow = false;
                    }
                }
            }

            // 가격 필터
            if (minPrice || maxPrice) {
                const cardPrice = parseInt(card.dataset.price);
                if (minPrice && cardPrice < parseInt(minPrice)) shouldShow = false;
                if (maxPrice && cardPrice > parseInt(maxPrice)) shouldShow = false;
            }

            // 평점 필터
            if (minRating || maxRating) {
                const cardRating = parseFloat(card.dataset.rating);
                if (minRating && cardRating < parseFloat(minRating)) shouldShow = false;
                if (maxRating && cardRating > parseFloat(maxRating)) shouldShow = false;
            }

            // 브랜드 필터
            if (selectedBrands.length > 0) {
                const cardBrand = card.dataset.brand.toLowerCase();
                if (!selectedBrands.some(brand => cardBrand.includes(brand.toLowerCase()))) {
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

        // 소분류가 선택되었는지 확인
        const selectedTopSubcategories = Array.from(document.querySelectorAll('input[name="top_subcategory"]:checked')).map(cb => cb.value);
        const selectedBottomSubcategories = Array.from(document.querySelectorAll('input[name="bottom_subcategory"]:checked')).map(cb => cb.value);
        const selectedSkirtSubcategories = Array.from(document.querySelectorAll('input[name="skirt_subcategory"]:checked')).map(cb => cb.value);
        const allSelectedSubcategories = [...selectedTopSubcategories, ...selectedBottomSubcategories, ...selectedSkirtSubcategories];

        // 선택된 필터들 수집 (소분류가 선택된 경우 의류 타입은 제외)
        document.querySelectorAll('.filter-checkbox:checked').forEach(cb => {
            const filterText = cb.parentElement.textContent.trim();
            const filterType = this.getFilterType(cb);
            
            // 소분류가 선택된 경우 의류 타입 필터는 제외
            if (allSelectedSubcategories.length > 0 && filterType === 'clothing_type') {
                return; // 이 필터는 건너뛰기
            }
            
            activeFilters.push({
                text: filterText,
                type: filterType,
                element: cb
            });
        });

        const minPrice = document.getElementById('min-price').value;
        const maxPrice = document.getElementById('max-price').value;
        if (minPrice || maxPrice) {
            activeFilters.push({
                text: `가격: ${minPrice || '0'}원 ~ ${maxPrice || '∞'}원`,
                type: 'price',
                element: null
            });
        }

        const minRating = document.getElementById('min-rating').value;
        const maxRating = document.getElementById('max-rating').value;
        if (minRating || maxRating) {
            activeFilters.push({
                text: `평점: ${minRating || '0'} ~ ${maxRating || '5'}점`,
                type: 'rating',
                element: null
            });
        }

        // 브랜드 필터 수집
        const brandSearchTerm = this.brandSearch.value.trim();
        if (brandSearchTerm) {
            activeFilters.push({
                text: `브랜드: ${brandSearchTerm}`,
                type: 'brand',
                element: null
            });
        }

        // 활성 필터 표시
        if (activeFilters.length > 0) {
            activeFiltersContainer.innerHTML = `
                <div class="active-filter-tags">
                    ${activeFilters.map(filter => `
                        <span class="filter-tag" data-filter-type="${filter.type}">
                            ${filter.text}
                            <button class="remove-filter" onclick="window.productFilter.removeFilter('${filter.type}')">×</button>
                        </span>
                    `).join('')}
                </div>
            `;
        } else {
            activeFiltersContainer.innerHTML = '';
        }
    }

    getFilterType(checkbox) {
        const name = checkbox.name;
        if (name === 'gender') return 'gender';
        if (name === 'clothing_type') return 'clothing_type';
        if (name === 'top_subcategory' || name === 'bottom_subcategory' || name === 'skirt_subcategory') return 'subcategory';
        return 'other';
    }

    removeFilter(filterType) {
        switch(filterType) {
            case 'gender':
                document.querySelectorAll('input[name="gender"]:checked').forEach(cb => cb.checked = false);
                break;
            case 'clothing_type':
                document.querySelectorAll('input[name="clothing_type"]:checked').forEach(cb => cb.checked = false);
                // Hide all subcategory sections
                document.getElementById('top-subcategories').style.display = 'none';
                document.getElementById('bottom-subcategories').style.display = 'none';
                document.getElementById('skirt-subcategories').style.display = 'none';
                break;
            case 'subcategory':
                document.querySelectorAll('input[name="top_subcategory"]:checked, input[name="bottom_subcategory"]:checked, input[name="skirt_subcategory"]:checked').forEach(cb => cb.checked = false);
                break;
            case 'price':
                document.getElementById('min-price').value = '';
                document.getElementById('max-price').value = '';
                break;
            case 'rating':
                document.getElementById('min-rating').value = '';
                document.getElementById('max-rating').value = '';
                break;
            case 'brand':
                this.brandSearch.value = '';
                break;
        }
        this.applyFilters();
    }

    clearAllFilters() {
        document.querySelectorAll('.filter-checkbox').forEach(cb => cb.checked = false);
        document.getElementById('min-price').value = '';
        document.getElementById('max-price').value = '';
        document.getElementById('min-rating').value = '';
        document.getElementById('max-rating').value = '';
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