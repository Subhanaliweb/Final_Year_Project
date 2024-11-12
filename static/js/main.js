jQuery(".hamburger").click(function () {
  jQuery(".headerMenu ul").slideToggle().css("display", "flex");
});

setTimeout(() => {
  let resultCount = jQuery(".results li").length;
  jQuery(".resultCount").text(resultCount);
}, 200);


function runNLPRegression() {
  fetch('/run-nlp-regression', {
      method: 'POST'
  })
  .then(response => response.json())
  .then(data => {
      alert(data.message);
  })
  .catch(error => console.error('Error:', error));
}