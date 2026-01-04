# app.py
import streamlit as st
from mof_matcher import load_mof_data, find_matching_mofs, INPUT_COLS

@st.cache_data
def get_data():
    return load_mof_data()


def main():
    st.set_page_config(page_title="MOF Adsorption Tool", layout="wide")

    st.title("MOF Adsorption Matching Tool")
    st.write(
        """
        Enter any subset of the parameters below.  
        For numeric entries, the tool searches for MOF records whose values lie within ±2% of your input.
        """
    )

    df = get_data()

    with st.expander("Preview of underlying MOF dataset", expanded=False):
        st.dataframe(df.head(20))

    # Input form
    with st.form("mof_search_form"):
        st.subheader("Search criteria")

        input_values = {}
        cols_per_row = 3

        for i in range(0, len(INPUT_COLS), cols_per_row):
            row_cols = st.columns(cols_per_row)
            for col_st, field_name in zip(row_cols, INPUT_COLS[i:i + cols_per_row]):
                with col_st:
                    user_val = st.text_input(
                        field_name,
                        value="",
                        key=f"input_{field_name}"
                    )
                    input_values[field_name] = user_val

        submitted = st.form_submit_button("Search MOFs")

    if submitted:
        # Parse inputs: numeric where possible, string otherwise
        parsed_inputs = {}
        for col_name, val in input_values.items():
            if val is None:
                continue
            val = val.strip()
            if not val:
                continue
            try:
                parsed_inputs[col_name] = float(val)
            except ValueError:
                parsed_inputs[col_name] = val

        if not parsed_inputs:
            st.warning("Please provide at least one non-empty input before searching.")
            return

        try:
            with st.spinner("Matching MOFs based on your criteria..."):
                df_data = get_data()
                result_df = find_matching_mofs(df_data, parsed_inputs)
        except KeyError as e:
            st.error(f"Column error: {e}")
            return
        except Exception as e:
            st.error(f"Unexpected error during matching: {e}")
            return

        if result_df.empty:
            st.info("No matching MOF records were found for the specified criteria.")
        else:
            st.success(f"Found {len(result_df)} matching MOF record(s).")
            st.dataframe(result_df)

            # Allow users to download the results
            csv = result_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download results as CSV",
                data=csv,
                file_name="mof_matches.csv",
                mime="text/csv",
            )


if __name__ == "__main__":
    main()
