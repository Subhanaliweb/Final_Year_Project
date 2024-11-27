jQuery(document).ready(function () {
  jQuery(".hamburger").click(function () {
    jQuery(".headerMenu ul").slideToggle().css("display", "flex");
  });

  setTimeout(() => {
    let resultCount = jQuery(".results li").length;
    jQuery(".resultCount").text(resultCount);
  }, 200);



  // Search Page JS
  $("#listingForm").on("submit", function (e) {
    e.preventDefault();  

    let form = $(this);
    let formData = new FormData(this);

    let keywords = formData.get("keywords").trim();
    if (!keywords) {
      alert("Please enter keywords for the search.");
      return;
    }

    let sellerTypes = formData.getAll("seller_types[]");
    let sellerCountries = formData.getAll("seller_countries[]").filter(val => val); 

    let filterParameters = [];
    if (sellerTypes.length > 0) {
      filterParameters.push("seller_level%3A" + sellerTypes.join("%2C")); 
    }
    if (sellerCountries.length > 0) {
      filterParameters.push("seller_location%3A" + sellerCountries.join("%2C")); 
    }

    let refParam = filterParameters.length > 0 ? "&ref=" + filterParameters.join("%7C") : "";

    let sourceParam = filterParameters.length > 0 ? "&source=drop_down_filters" : "";

    // Final URL
    let finalUrl = `https://www.fiverr.com/search/gigs?query=${encodeURIComponent(keywords)}${sourceParam}${refParam}`;

    let finalUrlInput = $('<input>').attr({
      type: 'hidden',
      name: 'finalUrl',
      value: finalUrl
    });

    form.append(finalUrlInput);

    form.off('submit').submit();

  });


  // Analysis Page JS
  $("#analysisFiltersForm").on("submit", function (e) {
    e.preventDefault();

    const listingsStarted = document.getElementById('listings-started').value;
    const salesCount = document.getElementById('sales-count').value;
    const rating = document.getElementById('rating').value;

    if (!listingsStarted && !salesCount && !rating) {
      setTimeout(function () {
        alert("No filters applied!");
      }, 1000);
      return; 
    }

    const filterData = {
      listings_started: listingsStarted,
      sales_count: salesCount,
      rating: rating
    };
    console.log(filterData);

    $.ajax({
      url: '/custom-filters',
      type: 'POST',
      contentType: 'application/json',
      data: JSON.stringify(filterData),
      success: function (response) {
        console.log('Server response:', response);
        alert("Filters applied successfully!");
      },
      error: function (error) {
        console.error('Error:', error);
        alert("An error occurred while applying the filters.");
      }
    });
  });

});
function handleFileOperation(filePath, operation) {
  const endpoints = {
    'nlp-regression': '/run-nlp-regression',
    'filtered-results': '/view-filtered-results'
  };

  fetch(endpoints[operation], {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: filePath })
  })
    .then(response => response.json())
    .then(data => {
      alert(data.message); 
    })
    .catch(error => {
      console.error('Error:', error);
      alert('Something went wrong: ' + error.message);
    });
}








