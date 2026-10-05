import streamlit as st
import pdfplumber
import pandas as pd
import numpy as np
import re
import io

import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak
)


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="EV Energy Consumption Comparison",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ EV Energy Consumption Report Comparison")

st.markdown(
    """
    **Upload two Energy Consumption PDF reports to compare
    vehicle energy consumption, regeneration and auxiliary loads.**
    """
)


# =========================================================
# PDF TEXT EXTRACTION
# =========================================================

def extract_pdf_text(pdf_file):

    text = ""

    with pdfplumber.open(pdf_file) as pdf:

        for page in pdf.pages:

            page_text = page.extract_text()

            if page_text:
                text += "\n" + page_text

    return text


# =========================================================
# EXTRACT TABLES
# =========================================================

def extract_pdf_tables(pdf_file):

    tables = []

    with pdfplumber.open(pdf_file) as pdf:

        for page_number, page in enumerate(pdf.pages):

            extracted = page.extract_tables()

            for table in extracted:

                if table:

                    df = pd.DataFrame(table)

                    df = df.dropna(
                        how="all"
                    )

                    df = df.dropna(
                        axis=1,
                        how="all"
                    )

                    if not df.empty:

                        tables.append(
                            {
                                "page": page_number + 1,
                                "table": df
                            }
                        )

    return tables


# =========================================================
# CLEAN NUMBER
# =========================================================

def clean_number(value):

    if value is None:
        return None

    value = str(value)

    value = value.replace(",", "")
    value = value.replace("kWh", "")
    value = value.replace("km", "")
    value = value.replace("%", "")
    value = value.strip()

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        value
    )

    if match:

        try:
            return float(match.group())

        except:
            return None

    return None


# =========================================================
# SEARCH PARAMETER
# =========================================================

def find_parameter_value(text, parameter_names):

    lines = text.splitlines()

    for line in lines:

        line_lower = line.lower()

        for parameter in parameter_names:

            if parameter.lower() in line_lower:

                # Look for number after parameter

                match = re.search(
                    r"(-?\d+(?:\.\d+)?)",
                    line
                )

                if match:

                    return float(
                        match.group(1)
                    )

    return None


# =========================================================
# PARAMETER DEFINITIONS
# =========================================================

PARAMETERS = {

    "Distance (km)": [
        "Distance",
        "Total Distance"
    ],

    "Average Speed (km/h)": [
        "Average Speed"
    ],

    "Maximum Speed (km/h)": [
        "Maximum Speed",
        "Max Speed"
    ],

    "HV Pack A Consumption (kWh)": [
        "Pack A Consumption",
        "HV Pack A Consumption"
    ],

    "HV Pack B Consumption (kWh)": [
        "Pack B Consumption",
        "HV Pack B Consumption"
    ],

    "HV Pack C Consumption (kWh)": [
        "Pack C Consumption",
        "HV Pack C Consumption"
    ],

    "HV Pack D Consumption (kWh)": [
        "Pack D Consumption",
        "HV Pack D Consumption"
    ],

    "Motor Consumption (kWh)": [
        "Motor Consumption"
    ],

    "DC-DC Consumption (kWh)": [
        "DC-DC Consumption",
        "DCDC Consumption"
    ],

    "Auxiliary Consumption (kWh)": [
        "Auxiliary Consumption",
        "Aux Consumption"
    ],

    "BCS Consumption (kWh)": [
        "BCS Consumption"
    ],

    "Total Consumption (kWh)": [
        "Total Consumption"
    ],

    "Braking Regen (kWh)": [
        "Braking Regen",
        "Braking Regeneration"
    ],

    "Coasting Regen (kWh)": [
        "Coasting Regen",
        "Coasting Regeneration"
    ],

    "Lift-off Regen (kWh)": [
        "Lift-off Regen",
        "Lift Off Regen",
        "Lift-off Regeneration"
    ],

    "Total Regeneration (kWh)": [
        "Total Regeneration",
        "Total Regen"
    ],

    "Net Energy (kWh)": [
        "Net Energy"
    ],

    "Energy Consumption (kWh/km)": [
        "Energy Consumption",
        "EC (kWh/km)",
        "EC"
    ]
}


# =========================================================
# EXTRACT PARAMETERS
# =========================================================

def extract_parameters(text):

    result = {}

    for parameter, names in PARAMETERS.items():

        result[parameter] = find_parameter_value(
            text,
            names
        )

    return result


# =========================================================
# COMPARE DATA
# =========================================================

def create_comparison(data1, data2):

    rows = []

    for parameter in PARAMETERS.keys():

        value1 = data1.get(parameter)
        value2 = data2.get(parameter)

        difference = None
        percentage = None

        if (
            value1 is not None
            and value2 is not None
        ):

            difference = value2 - value1

            if value1 != 0:

                percentage = (
                    difference /
                    abs(value1)
                ) * 100

        rows.append(
            {
                "Parameter": parameter,
                "Report 1": value1,
                "Report 2": value2,
                "Difference": difference,
                "% Difference": percentage
            }
        )

    return pd.DataFrame(rows)


# =========================================================
# ENGINEERING OBSERVATIONS
# =========================================================

def generate_observations(df):

    observations = []

    for _, row in df.iterrows():

        parameter = row["Parameter"]

        v1 = row["Report 1"]
        v2 = row["Report 2"]

        diff = row["Difference"]
        pct = row["% Difference"]

        if (
            pd.isna(v1)
            or pd.isna(v2)
            or pd.isna(pct)
        ):
            continue

        if diff > 0:

            observations.append(
                f"{parameter} increased by "
                f"{abs(diff):.2f} "
                f"({abs(pct):.2f}%) "
                f"in Report 2."
            )

        elif diff < 0:

            observations.append(
                f"{parameter} decreased by "
                f"{abs(diff):.2f} "
                f"({abs(pct):.2f}%) "
                f"in Report 2."
            )

        else:

            observations.append(
                f"{parameter} remained unchanged."
            )

    return observations


# =========================================================
# CREATE BAR CHART
# =========================================================

def create_chart(df, filename):

    valid_df = df.dropna(
        subset=["Report 1", "Report 2"]
    )

    if valid_df.empty:
        return None

    plt.figure(
        figsize=(10, 6)
    )

    x = np.arange(
        len(valid_df)
    )

    width = 0.35

    plt.bar(
        x - width / 2,
        valid_df["Report 1"],
        width,
        label="Report 1"
    )

    plt.bar(
        x + width / 2,
        valid_df["Report 2"],
        width,
        label="Report 2"
    )

    plt.xticks(
        x,
        valid_df["Parameter"],
        rotation=45,
        ha="right"
    )

    plt.ylabel("Energy")
    plt.title(
        "Energy Consumption Comparison"
    )

    plt.legend()

    plt.tight_layout()

    plt.savefig(
        filename,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close()

    return filename


# =========================================================
# CREATE PDF REPORT
# =========================================================

def create_pdf_report(
    comparison_df,
    observations,
    chart_file
):

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=20,
        spaceAfter=20
    )

    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10
    )

    normal_style = styles["BodyText"]

    elements = []

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    elements.append(
        Paragraph(
            "EV Energy Consumption Comparison Report",
            title_style
        )
    )

    elements.append(
        Spacer(1, 10)
    )

    elements.append(
        Paragraph(
            "Comparison between Report 1 and Report 2",
            normal_style
        )
    )

    elements.append(
        Spacer(1, 20)
    )

    # -----------------------------------------------------
    # SUMMARY TABLE
    # -----------------------------------------------------

    elements.append(
        Paragraph(
            "1. Energy Consumption Comparison",
            heading_style
        )
    )

    table_data = [
        [
            "Parameter",
            "Report 1",
            "Report 2",
            "Difference",
            "% Difference"
        ]
    ]

    for _, row in comparison_df.iterrows():

        def fmt(value):

            if pd.isna(value):
                return "N/A"

            return f"{value:.2f}"

        table_data.append(
            [
                row["Parameter"],
                fmt(row["Report 1"]),
                fmt(row["Report 2"]),
                fmt(row["Difference"]),
                (
                    "N/A"
                    if pd.isna(
                        row["% Difference"]
                    )
                    else f'{row["% Difference"]:.2f}%'
                )
            ]
        )

    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[
            180,
            70,
            70,
            70,
            70
        ]
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.grey
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.black
                ),

                (
                    "ALIGN",
                    (1, 1),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                )
            ]
        )
    )

    elements.append(table)

    elements.append(
        PageBreak()
    )

    # -----------------------------------------------------
    # CHART
    # -----------------------------------------------------

    elements.append(
        Paragraph(
            "2. Graphical Comparison",
            heading_style
        )
    )

    if chart_file:

        elements.append(
            Image(
                chart_file,
                width=500,
                height=300
            )
        )

    elements.append(
        PageBreak()
    )

    # -----------------------------------------------------
    # OBSERVATIONS
    # -----------------------------------------------------

    elements.append(
        Paragraph(
            "3. Engineering Observations",
            heading_style
        )
    )

    for observation in observations:

        elements.append(
            Paragraph(
                "• " + observation,
                normal_style
            )
        )

        elements.append(
            Spacer(1, 6)
        )

    # -----------------------------------------------------
    # CONCLUSION
    # -----------------------------------------------------

    elements.append(
        Paragraph(
            "4. Conclusion",
            heading_style
        )

    # Find EC row

    ec_row = comparison_df[
        comparison_df["Parameter"]
        == "Energy Consumption (kWh/km)"
    ]

    if not ec_row.empty:

        ec1 = ec_row.iloc[0]["Report 1"]
        ec2 = ec_row.iloc[0]["Report 2"]

        if (
            not pd.isna(ec1)
            and not pd.isna(ec2)
        ):

            if ec2 > ec1:

                conclusion = (
                    f"Report 2 shows higher vehicle "
                    f"energy consumption than Report 1. "
                    f"EC increased from "
                    f"{ec1:.3f} kWh/km to "
                    f"{ec2:.3f} kWh/km."
                )

            elif ec2 < ec1:

                conclusion = (
                    f"Report 2 shows improved vehicle "
                    f"energy efficiency compared with "
                    f"Report 1. EC reduced from "
                    f"{ec1:.3f} kWh/km to "
                    f"{ec2:.3f} kWh/km."
                )

            else:

                conclusion = (
                    "Both reports show the same "
                    "energy consumption."
                )

        else:

            conclusion = (
                "Energy Consumption values were "
                "not available in both reports."
            )

    else:

        conclusion = (
            "Energy Consumption comparison could "
            "not be established."
        )

    elements.append(
        Paragraph(
            conclusion,
            normal_style
        )
    )

    doc.build(elements)

    buffer.seek(0)

    return buffer


# =========================================================
# FILE UPLOAD
# =========================================================

col1, col2 = st.columns(2)

with col1:

    st.subheader("📄 Report 1")

    pdf1 = st.file_uploader(
        "Upload EC Report 1",
        type=["pdf"],
        key="pdf1"
    )


with col2:

    st.subheader("📄 Report 2")

    pdf2 = st.file_uploader(
        "Upload EC Report 2",
        type=["pdf"],
        key="pdf2"
    )


# =========================================================
# MAIN PROCESS
# =========================================================

if pdf1 and pdf2:

    st.success(
        "Both reports uploaded successfully."
    )

    if st.button(
        "🔍 Compare Energy Consumption",
        type="primary"
    ):

        with st.spinner(
            "Extracting data from PDF reports..."
        ):

            text1 = extract_pdf_text(pdf1)

            text2 = extract_pdf_text(pdf2)

            data1 = extract_parameters(text1)

            data2 = extract_parameters(text2)

        # -------------------------------------------------
        # COMPARISON
        # -------------------------------------------------

        comparison_df = create_comparison(
            data1,
            data2
        )

        # -------------------------------------------------
        # DATA EXTRACTION
        # -------------------------------------------------

        st.header(
            "1️⃣ Extracted EC Data"
        )

        extracted_df = comparison_df[
            [
                "Parameter",
                "Report 1",
                "Report 2"
            ]
        ]

        st.dataframe(
            extracted_df,
            use_container_width=True,
            hide_index=True
        )

        # -------------------------------------------------
        # DIFFERENCE
        # -------------------------------------------------

        st.header(
            "2️⃣ Difference & % Difference"
        )

        display_df = comparison_df.copy()

        display_df[
            "Difference"
        ] = display_df[
            "Difference"
        ].round(3)

        display_df[
            "% Difference"
        ] = display_df[
            "% Difference"
        ].round(2)

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        # -------------------------------------------------
        # ENERGY CONSUMPTION
        # -------------------------------------------------

        st.header(
            "3️⃣ Energy Consumption Comparison"
        )

        energy_parameters = [
            "HV Pack A Consumption (kWh)",
            "HV Pack B Consumption (kWh)",
            "HV Pack C Consumption (kWh)",
            "HV Pack D Consumption (kWh)",
            "Motor Consumption (kWh)",
            "DC-DC Consumption (kWh)",
            "Auxiliary Consumption (kWh)",
            "BCS Consumption (kWh)",
            "Total Consumption (kWh)",
            "Net Energy (kWh)",
            "Energy Consumption (kWh/km)"
        ]

        energy_df = comparison_df[
            comparison_df["Parameter"].isin(
                energy_parameters
            )
        ]

        st.dataframe(
            energy_df,
            use_container_width=True,
            hide_index=True
        )

        # -------------------------------------------------
        # REGENERATION
        # -------------------------------------------------

        st.header(
            "4️⃣ Regeneration Comparison"
        )

        regen_parameters = [
            "Braking Regen (kWh)",
            "Coasting Regen (kWh)",
            "Lift-off Regen (kWh)",
            "Total Regeneration (kWh)"
        ]

        regen_df = comparison_df[
            comparison_df["Parameter"].isin(
                regen_parameters
            )
        ]

        st.dataframe(
            regen_df,
            use_container_width=True,
            hide_index=True
        )

        # -------------------------------------------------
        # GRAPH
        # -------------------------------------------------

        st.header(
            "5️⃣ Graph Comparison"
        )

        chart_df = comparison_df[
            comparison_df["Parameter"].isin(
                energy_parameters
            )
        ]

        chart_df = chart_df.dropna(
            subset=[
                "Report 1",
                "Report 2"
            ]
        )

        if not chart_df.empty:

            chart_display = chart_df[
                [
                    "Parameter",
                    "Report 1",
                    "Report 2"
                ]
            ].set_index(
                "Parameter"
            )

            st.bar_chart(
                chart_display
            )

        # -------------------------------------------------
        # OBSERVATIONS
        # -------------------------------------------------

        st.header(
            "6️⃣ Engineering Observations"
        )

        observations = generate_observations(
            comparison_df
        )

        for observation in observations:

            st.write(
                "• " + observation
            )

        # -------------------------------------------------
        # PDF GENERATION
        # -------------------------------------------------

        st.header(
            "7️⃣ Download Combined Comparison Report"
        )

        chart_file = "energy_comparison_chart.png"

        create_chart(
            energy_df,
            chart_file
        )

        pdf_report = create_pdf_report(
            comparison_df,
            observations,
            chart_file
        )

        st.download_button(
            label="📥 Download Combined Comparison PDF",
            data=pdf_report,
            file_name="EV_Energy_Consumption_Comparison.pdf",
            mime="application/pdf"
        )

else:

    st.info(
        "Please upload both EC PDF reports."
    )