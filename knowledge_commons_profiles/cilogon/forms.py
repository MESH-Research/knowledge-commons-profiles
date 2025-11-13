from __future__ import annotations

from django import forms


class UploadCSVForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV file", help_text="Upload a CSV file with a header row."
    )

    def clean_csv_file(self):
        f = self.cleaned_data["csv_file"]

        # Basic sanity checks
        if not f.name.lower().endswith(".csv"):
            msg = "Please upload a .csv file."
            raise forms.ValidationError(msg)

        # Optional: check MIME type if you want to be stricter
        # if f.content_type not in ("text/csv", "application/vnd.ms-excel"):
        #     raise forms.ValidationError("File does not look like a CSV.")

        return f
