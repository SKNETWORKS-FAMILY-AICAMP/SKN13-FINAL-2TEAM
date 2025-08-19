document.addEventListener('DOMContentLoaded', function() {
    console.log("filters.js 스크립트 시작");

    try {
        const productGrid = document.getElementById('product-grid');
        const paginationContainer = document.getElementById('pagination-container');
        const noResults = document.getElementById('no-results');
        const applyFiltersBtn = document.getElementById('apply-filters');
        const clearFiltersBtn = document.getElementById('clear-filters');

        if (!productGrid || !paginationContainer || !noResults || !applyFiltersBtn || !clearFiltersBtn) {
            console.error("필수 HTML 요소 중 일부를 찾을 수 없습니다. ID를 확인해주세요.");
            return;
        }

        let state = {
            currentPage: 1,
            filters: getFilterValues()
        };

        function getFilterValues() {
            const selectedGenders = Array.from(document.querySelectorAll('input[name="gender"]:checked')).map(cb => cb.value);
            const selectedTypes = Array.from(document.querySelectorAll('input[name="clothing_type"]:checked')).map(cb => cb.value);
            
            const selectedTopSub = Array.from(document.querySelectorAll('input[name="top_subcategory"]:checked')).map(cb => cb.value);
            const selectedBottomSub = Array.from(document.querySelectorAll('input[name="bottom_subcategory"]:checked')).map(cb => cb.value);
            const selectedSkirtSub = Array.from(document.querySelectorAll('input[name="skirt_subcategory"]:checked')).map(cb => cb.value);
            const allSubcategories = [...selectedTopSub, ...selectedBottomSub, ...selectedSkirtSub];

            return {
                gender: selectedGenders.length > 0 ? selectedGenders.join(',') : null,
                clothing_type: allSubcategories.length > 0 ? null : (selectedTypes.length > 0 ? selectedTypes.join(',') : null),
                subcategory: allSubcategories.length > 0 ? allSubcategories.join(',') : null,
                min_price: document.getElementById('min-price').value || null,
                max_price: document.getElementById('max-price').value || null,
                min_rating: document.getElementById('min-rating').value || null,
                brand: document.getElementById('brand-search').value.trim() || null
            };
        }

        async function fetchProducts(page = 1) {
            console.log(`Fetching products for page: ${page}`);
            state.currentPage = page;
            state.filters = getFilterValues();

            const params = new URLSearchParams();
            params.append('page', state.currentPage);
            params.append('limit', 20);

            for (const [key, value] of Object.entries(state.filters)) {
                if (value) {
                    params.append(key, value);
                }
            }

            try {
                const response = await fetch(`/products/api/products?${params.toString()}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                console.log("API 응답 데이터:", data);

                renderProducts(data.products);
                renderPagination(data.page, data.total_pages);

                if (data.products.length === 0) {
                    noResults.style.display = 'block';
                } else {
                    noResults.style.display = 'none';
                }

            } catch (error) {
                console.error('Error fetching products:', error);
                productGrid.innerHTML = '<p>상품을 불러오는 데 실패했습니다. 개발자 콘솔을 확인해주세요.</p>';
            }
        }

        function createProductCard(product) {
            const card = document.createElement('div');
            card.className = 'product-card';
            
            const rating = parseFloat(product.평점 || 0);
            let stars = '';
            for (let i = 0; i < 5; i++) {
                stars += (rating >= i + 0.5) ? '★' : '☆';
            }

            card.innerHTML = `
                <img src="${product.대표이미지URL || product.사진}" alt="${product.상품명}">
                <div class="product-card-content">
                    <h3>${product.제품이름}</h3>
                    <p class="brand">${product.브랜드 || ''}</p>
                    <p class="price">${product.가격}</p>
                    <button class="add-to-cart">장바구니에 추가</button>
                </div>
            `;
            return card;
        }

        function renderProducts(products) {
            productGrid.innerHTML = '';
            if (products) {
                products.forEach(product => {
                    const card = createProductCard(product);
                    productGrid.appendChild(card);
                });
            }
        }

        function renderPagination(currentPage, totalPages) {
            console.log(`Rendering pagination: currentPage=${currentPage}, totalPages=${totalPages}`);
            paginationContainer.innerHTML = '';
            if (totalPages <= 1) {
                console.log("총 페이지가 1 이하여서 페이지네이션을 렌더링하지 않습니다.");
                return;
            }

            const createPageLink = (page, text = page, isDisabled = false, isActive = false) => {
                const li = document.createElement('li');
                li.className = 'page-item';
                if (isDisabled) li.classList.add('disabled');
                if (isActive) li.classList.add('active');

                const a = document.createElement('a');
                a.className = 'page-link';
                a.href = '#';
                a.textContent = text;
                if (page > 0) a.dataset.page = page;
                li.appendChild(a);
                return li;
            };

            const ul = document.createElement('ul');
            ul.className = 'pagination';

            ul.appendChild(createPageLink(currentPage - 1, '이전', currentPage === 1));

            let startPage = Math.max(1, currentPage - 2);
            let endPage = Math.min(totalPages, currentPage + 2);

            if (currentPage <= 3) endPage = Math.min(5, totalPages);
            if (currentPage > totalPages - 3) startPage = Math.max(1, totalPages - 4);

            if (startPage > 1) {
                ul.appendChild(createPageLink(1, '1'));
                if (startPage > 2) ul.appendChild(createPageLink(0, '...', true));
            }

            for (let i = startPage; i <= endPage; i++) {
                ul.appendChild(createPageLink(i, i, false, i === currentPage));
            }

            if (endPage < totalPages) {
                if (endPage < totalPages - 1) ul.appendChild(createPageLink(0, '...', true));
                ul.appendChild(createPageLink(totalPages, totalPages));
            }

            ul.appendChild(createPageLink(currentPage + 1, '다음', currentPage === totalPages));

            paginationContainer.appendChild(ul);
            console.log("페이지네이션 렌더링 완료.");
        }

        applyFiltersBtn.addEventListener('click', (e) => {
            e.preventDefault();
            fetchProducts(1);
        });

        clearFiltersBtn.addEventListener('click', () => {
            document.querySelectorAll('.filter-checkbox').forEach(cb => cb.checked = false);
            document.getElementById('min-price').value = '';
            document.getElementById('max-price').value = '';
            document.getElementById('min-rating').value = '';
            document.getElementById('max-rating').value = '';
            document.getElementById('brand-search').value = '';
            fetchProducts(1);
        });

        paginationContainer.addEventListener('click', function(e) {
            e.preventDefault();
            const target = e.target;
            if (target.tagName === 'A' && target.dataset.page && !target.closest('.disabled') && !target.closest('.active')) {
                const page = parseInt(target.dataset.page, 10);
                if (page > 0) {
                    fetchProducts(page);
                    window.scrollTo(0, 0);
                }
            }
        });

        fetchProducts(1);

    } catch (error) {
        console.error("스크립트 초기화 중 심각한 오류 발생:", error);
        alert("페이지 스크립트 실행 중 오류가 발생했습니다. F12를 눌러 개발자 콘솔을 확인해주세요.");
    }
});
