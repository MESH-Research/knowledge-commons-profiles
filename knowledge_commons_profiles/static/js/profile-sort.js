$(document).ready(function() {

  const csrftoken = $("[name='csrfmiddlewaretoken']")[0].value;

  function saveOrder(itemOrder, side) {
    let url = "";

    if (side == "left") {
        url = document.querySelector('[id=save-profile-left]').value;
    } else {
        url = document.querySelector('[id=save-profile-right]').value;
    }

    // Send AJAX request to save the order
    $.ajax({
        url: url,
        type: 'POST',
        contentType: 'application/json',
        headers: {'X-CSRFToken': csrftoken},
        mode: 'same-origin',
        data: JSON.stringify({
            'item_order': itemOrder,
        }),
        success: function(response) {
            console.log('Order saved successfully:', response);
        },
        error: function(xhr, status, error) {
            console.error('Error saving order:', error);
        }
    });
  }

  $("#left_column").sortable({
    update: function (event, ui) {
      // Get the current order after sorting
      var itemOrder = [];
      $("#left_column div.sortable-item").each(function () {
        // Extract the item ID from the div id attribute
        var itemId = $(this).attr('id');
        itemOrder.push(itemId);
      });

      // Send the new order to the server
      saveOrder(itemOrder, "left");
    },
    start: function (e, ui) {
      $(ui.item).find('.tinymce').each(function () {
        tinymce.get($(this).attr('id')).remove();
      });
    },
    stop: function (e, ui) {
      $(ui.item).find('.tinymce').each(function () {
        tinymce.init({
          license_key: "gpl",
          selector: '#' + $(this).attr('id'),
          height: 360,
          width: "100%",
          custom_undo_redo_levels: 20,
          theme: "silver",
          plugins: "save link image media preview table code lists fullscreen insertdatetime nonbreaking directionality searchreplace wordcount visualblocks visualchars code fullscreen autolink lists charmap anchor pagebreak",
          toolbar1: "fullscreen preview bold italic underline | fontselect, fontsizeselect | forecolor backcolor | alignleft alignright | aligncenter alignjustify | indent outdent | bullist numlist table | | link | code",
          contextmenu: "formats | link image",
          menubar: false,
          statusbar: true,
          promotion: false,
          forced_root_block: " ",
        });
      });
    }
  });

  $("#right_column").sortable({
    update: function (event, ui) {
      // Get the current order after sorting
      var itemOrder = [];
      $("#right_column div.sortable-item").each(function () {
        // Extract the item ID from the div id attribute
        var itemId = $(this).attr('id');
        itemOrder.push(itemId);
      });

      // Send the new order to the server
      saveOrder(itemOrder, "right");
    }
  });
});
