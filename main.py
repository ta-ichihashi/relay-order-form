import streamlit as st
import pandas as pd
import re
from streamlit_gsheets import GSheetsConnection
from dataclasses import dataclass, field
from collections import Counter



@dataclass
class TeamGroup:
    group_name : str
    df         : pd.DataFrame
    new_order_df : pd.DataFrame = field(default_factory=pd.DataFrame)
    editet_runners     : list = field(default_factory=list)

    def __post_init__(self):
        self.group_df = self.get_group_df()
        self.new_order_df = self.group_df.copy()
        self.editet_runners = self.group_df["氏名"].tolist()
        self.pattern = self.group_df[["ナンバー","走順"]].reset_index(drop=True).values.tolist()

    def get_group_df(self) -> pd.DataFrame:
        return self.df.loc[self.df["団"] == self.group_name].sort_values(["チーム", "走順"])

    def set_order(self, team : str, team_code : str, order1 : str, order2 : str, order3 : str):
        team_order_df = self.new_order_df.query(
            f'氏名 == "{order1}" | 氏名 == "{order2}" | 氏名 == "{order3}" | チーム == "{team}"'
            )
        duplicated_df = team_order_df[team_order_df.duplicated(subset="競技者番号", keep=False)]
        duplicated_df = duplicated_df.loc[duplicated_df["チームコード"] != team_code]
        team_order_df = team_order_df.drop(duplicated_df.index)
        team_order_df["走順"] = None
        team_order_df["チーム"] = team
        team_order_df["チームコード"] = team_code
        team_order_df.loc[(self.new_order_df["氏名"] == order1), ["走順"]] = 1
        team_order_df.loc[(self.new_order_df["氏名"] == order2), ["走順"]] = 2
        team_order_df.loc[(self.new_order_df["氏名"] == order3), ["走順"]] = 3
        team_order_df = team_order_df.sort_values("走順")
        for i in range(len(team_order_df)):
            column_number = team_order_df.columns.get_loc("ナンバー")
            team_order_df.iloc[i, column_number] = team_code + str(i + 1)
        self.new_order_df.loc[team_order_df.index] = team_order_df
        self.new_order_df = self.new_order_df.sort_values("走順")
        self.new_order_df = self.new_order_df.sort_values(["チーム", "走順"])

    def get_new_runners(self) -> list:
        return self.new_order_df["氏名"].values.tolist()

    def get_new_team_members(self) -> dict:
        df = self.new_order_df.loc[:, ["チーム", "走順", "氏名", "競技者番号"]].groupby("チーム").apply(
            lambda x: x.drop("チーム", axis=1).to_dict('records')
        ).to_dict()
        return df

    def make_new_order_df(self, author:str, author_email:str):
        for i in range(len(self.new_order_df)):
            if (self.new_order_df.iloc[i] == self.group_df.iloc[i]).all():
                continue
            else:
                c = self.new_order_df.columns.get_loc("申請者氏名")
                self.new_order_df.iloc[i, c] = author
                c = self.new_order_df.columns.get_loc("申請者email")
                self.new_order_df.iloc[i, c] = author_email


@dataclass
class CompetitionClass:
    class_name  : str
    df          : pd.DataFrame

    def get_group_df(self) -> pd.DataFrame:
        return self.df.loc[self.df["クラス"] == self.class_name].sort_values(["チーム", "走順"])

@dataclass
class TeamOrder:
    team_name   : str
    class_name  : str
    group       : TeamGroup

    def __post_init__(self):
        self.team_df = self.get_team_df()

    def get_team_df(self) -> pd.DataFrame:
        group_df = self.group.get_group_df()
        return group_df.loc[group_df["チーム"] == self.team_name]

    def get_team_code(self) -> str:
        col_number = self.team_df.columns.get_loc("チームコード")
        return self.team_df.iat[0, col_number]

def main():
    # Google Sheets Authentication
    st.markdown('''
                ## 走順表
                ''')

    st.sidebar.markdown("### 全日本リレーオリエンテーリング大会走順届")

    conn = st.connection("gsheets", type=GSheetsConnection)

    df = conn.read(
        worksheet="走順シート申請",
        ttl=10,
        dtype=object
    )
    df = df.set_index("index")

    selected_class = st.sidebar.selectbox(
        "クラス",
        df["クラス"].unique(),
        index=None
    )

    selected_team_group = st.sidebar.selectbox(
            "選手団",
            df.loc[df["クラス"] == selected_class]["団"].unique(),
            index=None
    )

    st.sidebar.markdown('''
                ### 利用方法
                1. サイドバーからクラスと選手団を選んでください。トップに現在の走順が表示されます。変更がなければこのまま終了してください。
                2. 変更したいチームの走順を設定します。
                3. 確認ボタンを押すと変更後の表が下部に現れます。
                4. 表の内容に問題なければ登録ボタンを押してください。
                ''')

    competition_class = CompetitionClass(
        class_name=selected_class,
        df=df
        )
    team_group = TeamGroup(
        group_name=selected_team_group,
        df = competition_class.get_group_df()
        )
    group_filterd_df = team_group.get_group_df()
    #df_pivot = filterd_df.set_index(["クラス","チーム","走順"]).unstack("走順").swaplevel(axis=1).stack()
    st.dataframe(group_filterd_df[["チーム", "ナンバー","競技者番号", "氏名", "走順"]])
    team_list = group_filterd_df["チーム"].unique().tolist()

    if len(group_filterd_df) > 0:
        with st.form("order_form"):
            team_member_pointer = 0
            name = st.text_input("申請者氏名","")
            mail = st.text_input("email","")
            st.markdown("走順申請")
            for team_name in team_list:
                st.divider()
                team_order = TeamOrder(
                    team_name=team_name,
                    class_name=competition_class.class_name,
                    group=team_group,
                    )

                ### チーム毎の処理
                team_df = team_order.get_team_df()
                o1 = st.selectbox(f"{team_name}: 1走",
                                  group_filterd_df["氏名"],
                                  index=team_member_pointer)
                o2 = st.selectbox(f"{team_name}: 2走",
                                  group_filterd_df["氏名"],
                                  index=team_member_pointer + 1)
                o3 = st.selectbox(f"{team_name}: 3走",
                                  group_filterd_df["氏名"],
                                  index=team_member_pointer + 2)
                team_group.set_order(team_name, team_order.get_team_code(), o1, o2, o3)
                team_member_pointer = team_member_pointer + len(team_df)

            st.form_submit_button("確認")

        def check_email_format(author_email):
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return re.match(email_regex, author_email) is not None

        # データチェック
        new_group_df = team_group.new_order_df.loc[team_group.new_order_df["走順"] <= 3]
        sum_of_orders = new_group_df.groupby("チーム")["走順"].sum().to_dict()
        new_group_members = new_group_df["氏名"].values.tolist()
        if name in ("", "nan") or mail in ("", "nan"):
            st.error("申請者の氏名とメールアドレスを入力してください。")
        elif not check_email_format(mail):
            st.error("申請者のメールアドレスの書式が不正です。")
        elif len(new_group_members) != len(set(new_group_members)):
            # 全チームの1～3走で重複した名前がないかチェック
            duplicated_items = sorted([k for k, v in Counter(new_group_members).items() if v > 1], key=new_group_members.index)
            for duplicated in duplicated_items:
                st.error(f"{duplicated} が重複しています。")
        elif sum([sum_of_orders[k] for k in sum_of_orders]) % 6 != 0:
            # 全チーム1,2,3走が完成されているかどうかのチェック
            for team in sum_of_orders:
                if sum_of_orders[team] != 6:
                    st.error(f"{team} に重複した登録者があります。")
        else:
            team_group.make_new_order_df(name, mail)
            total_df = team_group.new_order_df[["チーム", "ナンバー","競技者番号", "氏名", "走順","申請者氏名","申請者email"]].set_index("ナンバー")
            st.write(total_df)

            if st.button("登録"):
                df = conn.read(
                            worksheet="走順シート申請",
                            ttl=10,
                            dtype=object

                        )
                df = df.set_index("index")
                df.loc[team_group.new_order_df.index] = team_group.new_order_df
                df = df.sort_values(["クラス", "チーム", "走順"])
                conn.update(
                    worksheet="走順シート申請",
                    data=df.reset_index()
                )
                st.success(f"{selected_team_group} 選手団の走順登録が完了しました")

# Print results.

if __name__ == "__main__":
    main()
