jQuery(".hamburger").click(function () {
  jQuery(".headerMenu ul").slideToggle().css("display", "flex");
});

setTimeout(() => {
  let resultCount = jQuery(".results li").length;
  jQuery(".resultCount").text(resultCount);
}, 200);

function runNLPRegression(filePath) {
  fetch('/run-nlp-regression', {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json',
      },
      body: JSON.stringify({ file_path: filePath })
  })
  .then(response => response.json())
  .then(data => {
      alert(data.message);  // Success message
  })
  .catch(error => {
      console.error('Error:', error);
      alert('Something went wrong: ' + error.message);
  });
}

// Filtered results function
function filteredResults(filePath) {
  // Assuming filteredDataFilePath is the path of the filtered CSV file

  fetch('/view-filtered-results', {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json',
      },
      body: JSON.stringify({ file_path: filePath })
  })
  .then(response => response.json())
  .then(data => {
      alert(data.message);  // Success message for filtered results
  })
  .catch(error => {
      console.error('Error:', error);
      alert('Something went wrong: ' + error.message);
  });
}
