document.addEventListener('DOMContentLoaded', function() {
    console.log("filters.js 스크립트 시작");

    try {
        const productGrid = document.getElementById('product-grid');
        const paginationContainer = document.querySelector('.pagination-container');
        const noResults = document.getElementById('no-results');
        const applyFiltersBtn = document.getElementById('apply-filters');
        const clearFiltersBtn = document.getElementById('clear-filters');

        if (!productGrid) {
            console.error("product-grid 요소를 찾을 수 없습니다.");
            return;
        }

        // 필터 값 가져오기
        function getFilterValues() {
            const selectedGenders = Array.from(document.querySelectorAll('input[name="gender"]:checked')).map(cb => cb.value);
            const selectedTypes = Array.from(document.querySelectorAll('input[name="clothing_type"]:checked')).map(cb => cb.value);
            
            return {
                gender: selectedGenders.length > 0 ? selectedGenders.join(',') : null,
                clothing_type: selectedTypes.length > 0 ? selectedTypes.join(',') : null,
                min_price: document.getElementById('min-price').value || null,
                max_price: document.getElementById('max-price').value || null,
                sort: document.getElementById('sort-select').value !== 'default' ? document.getElementById('sort-select').value : null
            };
        }

        // API를 통한 상품 가져오기
        async function fetchProducts(page = 1) {
            console.log(`Fetching products for page: ${page}`);
            
            // 로딩 상태 표시
            showLoading();
            
            const filters = getFilterValues();
            const params = new URLSearchParams();
            params.append('page', page);
            params.append('limit', 20);

            // 필터 파라미터 추가
            for (const [key, value] of Object.entries(filters)) {
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
                renderPagination(data.page, data.total_pages, data.total);
                updateResultsCount(data.total);

                if (data.products.length === 0) {
                    showNoResults();
                } else {
                    hideNoResults();
                }

            } catch (error) {
                console.error('Error fetching products:', error);
                showError('상품을 불러오는 중 오류가 발생했습니다.');
                // API 호출 실패 시 서버 사이드 렌더링으로 폴백
                setTimeout(() => {
                    applyFiltersToURL();
                }, 2000);
            } finally {
                hideLoading();
            }
        }

        // 서버 사이드 렌더링으로 폴백
        function applyFiltersToURL() {
            const filters = getFilterValues();
            const params = new URLSearchParams();
            params.append('page', '1'); // 필터 적용 시 첫 페이지로 이동

            for (const [key, value] of Object.entries(filters)) {
                if (value) {
                    params.append(key, value);
                }
            }

            // 페이지 이동
            window.location.href = '/products/?' + params.toString();
        }

        // 상품 카드 생성
        function createProductCard(product) {
            const card = document.createElement('div');
            card.className = 'product-card';
            
            // 데이터 속성 설정
            card.dataset.productId = product.상품코드 || '';
            card.dataset.productName = product.상품명 || '';
            card.dataset.productBrand = product.한글브랜드명 || product.브랜드 || '';
            card.dataset.productCategory = product.대분류 || '';
            card.dataset.productSubcategory = product.소분류 || '';
            card.dataset.productColor = product.색상 || '';
            card.dataset.productPrice = product.원가 || '0';
            card.dataset.productImage = product.이미지URL || product.대표이미지URL || '';
            card.dataset.productLink = product.상품링크 || '';
            card.dataset.type = product.의류타입 || product.대분류 || '';

            // 가격 포맷팅 (원가 사용)
            const price = product.원가 || 0;
            const formattedPrice = price.toLocaleString('ko-KR');

            card.innerHTML = `
                <img src="${product.이미지URL || product.대표이미지URL || ''}" 
                     alt="${product.상품명 || ''}"
                     title="${product.상품명 || ''}: ${product.한글브랜드명 || product.브랜드 || ''}">
            `;

            // 클릭 이벤트 추가
            card.addEventListener('click', function() {
                loadProductDetails(card);
                openModal();
            });

            return card;
        }

        // 상품 목록 렌더링
        function renderProducts(products) {
            productGrid.innerHTML = '';
            if (products && products.length > 0) {
                products.forEach(product => {
                    const card = createProductCard(product);
                    productGrid.appendChild(card);
                });
            }
        }

        // 페이지네이션 렌더링
        function renderPagination(currentPage, totalPages, totalProducts) {
            if (!paginationContainer) return;
            
            paginationContainer.innerHTML = '';
            
            if (totalPages <= 1) {
                return;
            }

            // 페이지네이션 정보
            const infoDiv = document.createElement('div');
            infoDiv.className = 'pagination-info';
            const itemsPerPage = 20;
            const startItem = (currentPage - 1) * itemsPerPage + 1;
            const endItem = Math.min(currentPage * itemsPerPage, totalProducts);
            infoDiv.innerHTML = `<span>총 ${totalProducts}개 상품 중 ${startItem}-${endItem}개 표시</span>`;
            paginationContainer.appendChild(infoDiv);

            // 페이지네이션 링크
            const paginationDiv = document.createElement('div');
            paginationDiv.className = 'pagination';

            // 처음/이전 버튼
            if (currentPage > 1) {
                paginationDiv.appendChild(createPageLink(1, '« 처음'));
                paginationDiv.appendChild(createPageLink(currentPage - 1, '‹ 이전'));
            }

            // 페이지 번호
            let startPage = Math.max(1, currentPage - 2);
            let endPage = Math.min(totalPages, currentPage + 2);

            if (currentPage <= 3) endPage = Math.min(5, totalPages);
            if (currentPage > totalPages - 3) startPage = Math.max(1, totalPages - 4);

            for (let i = startPage; i <= endPage; i++) {
                if (i === currentPage) {
                    paginationDiv.appendChild(createPageLink(i, i.toString(), true));
                } else {
                    paginationDiv.appendChild(createPageLink(i, i.toString()));
                }
            }

            // 다음/마지막 버튼
            if (currentPage < totalPages) {
                paginationDiv.appendChild(createPageLink(currentPage + 1, '다음 ›'));
                paginationDiv.appendChild(createPageLink(totalPages, '마지막 »'));
            }

            paginationContainer.appendChild(paginationDiv);
        }

        // 페이지 링크 생성
        function createPageLink(page, text, isCurrent = false) {
            const link = document.createElement('a');
            link.href = '#';
            link.className = 'page-link';
            if (isCurrent) link.classList.add('current');
            link.textContent = text;
            link.dataset.page = page;
            
            link.addEventListener('click', function(e) {
                e.preventDefault();
                if (!isCurrent) {
                    fetchProducts(page);
                    window.scrollTo(0, 0);
                }
            });
            
            return link;
        }

        // 결과 수 업데이트
        function updateResultsCount(total) {
            const header = document.querySelector('.listing-header h1');
            if (header) {
                header.textContent = `상품 목록 (${total}개)`;
            }
        }

        // 결과 없음 표시/숨김
        function showNoResults() {
            if (noResults) {
                noResults.style.display = 'block';
            }
        }

        function hideNoResults() {
            if (noResults) {
                noResults.style.display = 'none';
            }
        }

        // 로딩 상태 관리
        function showLoading() {
            if (productGrid) {
                productGrid.innerHTML = '<div class="loading">상품을 불러오는 중...</div>';
            }
        }

        function hideLoading() {
            // 로딩 상태는 renderProducts에서 자동으로 제거됨
        }

        // 에러 상태 관리
        function showError(message) {
            if (productGrid) {
                productGrid.innerHTML = `<div class="error">${message}</div>`;
            }
        }

        // 모달 관련 함수들
        function openModal() {
            const modal = document.getElementById('product-modal');
            if (modal) {
                modal.style.display = 'flex';
            }
        }

        function loadProductDetails(card) {
            const productDetails = document.getElementById('product-details');
            if (!productDetails) return;

            const productName = card.dataset.productName;
            const productBrand = card.dataset.productBrand;
            const productCategory = card.dataset.productCategory;
            const productSubcategory = card.dataset.productSubcategory;
            const productColor = card.dataset.productColor;
            const productPrice = card.dataset.productPrice;
            const productImage = card.dataset.productImage;
            const productLink = card.dataset.productLink;
            const productSite = card.dataset.productSite;
            const productType = card.dataset.type;

            // 가격 포맷팅 (원가 사용)
            function formatPrice(price) {
                if (!price || price === '0' || price === 'N/A') return 'N/A';
                const numPrice = parseInt(price);
                if (isNaN(numPrice)) return price;
                return numPrice.toLocaleString('ko-KR') + '원';
            }

            productDetails.innerHTML = `
                <div style="display:flex; gap:20px; margin-bottom:20px;">
                    <img src="${productImage || 'https://via.placeholder.com/200'}" 
                         alt="${productName}" 
                         style="width:200px; height:200px; object-fit:cover; border-radius:8px;">
                    <div style="flex:1;">
                        <h4 style="margin:0 0 15px 0; color:#333; font-size:18px; font-weight:600;">${productName}</h4>
                        <div style="background:#f8f9fa; padding:15px; border-radius:8px; margin-bottom:15px;">
                            <p style="margin:8px 0; color:#333; font-size:14px;"><strong style="color:#2c3e50;">브랜드:</strong> <span style="color:#34495e;">${productBrand || 'N/A'}</span></p>
                            <p style="margin:8px 0; color:#333; font-size:14px;"><strong style="color:#2c3e50;">카테고리:</strong> <span style="color:#34495e;">${productType || productCategory || 'N/A'} > ${productSubcategory || 'N/A'}</span></p>
                            <p style="margin:8px 0; color:#333; font-size:14px;"><strong style="color:#2c3e50;">색상:</strong> <span style="color:#34495e;">${productColor || 'N/A'}</span></p>
                            <p style="margin:8px 0; color:#333; font-size:14px;"><strong style="color:#2c3e50;">가격:</strong> <span style="color:#e74c3c; font-weight:600; font-size:16px;">${formatPrice(productPrice)}</span></p>
                            <p style="margin:8px 0; color:#333; font-size:14px;"><strong style="color:#2c3e50;">사이트:</strong> <span style="color:#34495e;">${productSite || 'N/A'}</span></p>
                        </div>
                        <div style="display:flex; gap:12px;">
                            ${productLink ? `<a href="${productLink}" target="_blank" style="flex:1; padding:12px 20px; background:linear-gradient(135deg, #3498db, #2980b9); color:#fff; text-decoration:none; border-radius:6px; font-weight:600; text-align:center; box-shadow:0 2px 8px rgba(52,152,219,0.3); transition:all 0.3s ease; white-space:nowrap;">상품 보기</a>` : ''}
                            <button onclick="addToJjim('${card.dataset.productId}')" style="flex:1; padding:12px 20px; background:linear-gradient(135deg, #e74c3c, #c0392b); color:#fff; border:none; border-radius:6px; font-weight:600; cursor:pointer; box-shadow:0 2px 8px rgba(231,76,60,0.3); transition:all 0.3s ease; white-space:nowrap;">❤️ 찜목록 추가</button>
                        </div>
                    </div>
                </div>
            `;
        }

        // 이벤트 리스너 설정
        if (applyFiltersBtn) {
            applyFiltersBtn.addEventListener('click', function(e) {
                e.preventDefault();
                fetchProducts(1);
            });
        }

        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', function() {
                // 모든 체크박스 해제
                document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
                // 가격 입력 필드 초기화
                document.getElementById('min-price').value = '';
                document.getElementById('max-price').value = '';
                // 정렬 초기화
                document.getElementById('sort-select').value = 'default';
                // 필터 적용
                fetchProducts(1);
            });
        }

        // 정렬 변경 시 자동 적용
        const sortSelect = document.getElementById('sort-select');
        if (sortSelect) {
            sortSelect.addEventListener('change', function() {
                fetchProducts(1);
            });
        }

        // 가격 버튼 클릭 이벤트
        document.querySelectorAll('.price-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const minPrice = this.dataset.min;
                const maxPrice = this.dataset.max;
                
                document.getElementById('min-price').value = minPrice;
                document.getElementById('max-price').value = maxPrice;
            });
        });

        // 모달 닫기 이벤트
        const modal = document.getElementById('product-modal');
        const closeBtn = document.getElementById('close-modal');
        
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                if (modal) modal.style.display = 'none';
            });
        }

        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    modal.style.display = 'none';
                }
            });
        }

        // 찜목록 추가 함수 (전역으로 노출)
        window.addToJjim = async function(productId) {
            if (!productId) {
                alert('상품 ID를 찾을 수 없습니다.');
                return;
            }

            try {
                const formData = new FormData();
                formData.append('product_id', productId);

                const response = await fetch('/preference/jjim', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    alert('찜목록에 추가되었습니다!');
                } else {
                    const result = await response.json();
                    if (result.message === '사용자 없음') {
                        alert('로그인이 필요합니다.');
                    } else {
                        alert(`찜목록 추가에 실패했습니다: ${result.message || '알 수 없는 오류'}`);
                    }
                }
            } catch (error) {
                console.error('Error adding to jjim:', error);
                alert('찜목록 추가 중 오류가 발생했습니다.');
            }
        };

        // 초기 로드
        fetchProducts(1);

    } catch (error) {
        console.error("스크립트 초기화 중 심각한 오류 발생:", error);
        alert("페이지 스크립트 실행 중 오류가 발생했습니다. F12를 눌러 개발자 콘솔을 확인해주세요.");
    }
});
