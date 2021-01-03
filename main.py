import discord
from discord.ext import commands

import asyncio
import sqlite3
import yaml
import datetime

import inspect
import math

import re

client = commands.Bot(command_prefix= "k!")

with open("config.yml") as f:
    conf = yaml.load(f)

TOKEN = conf["token"]

conn = sqlite3.connect("main.db")
cur = conn.cursor()


cur.execute("CREATE TABLE IF NOT EXISTS user_profile \
    (id integer PRIMARY KEY, user_id integer, custom_id text, nickname text, status_message text)")

# id : 0, user_id : 1, custom_id : 2, nickname : 3, status_message : 4

cur.execute("CREATE TABLE IF NOT EXISTS ask_messages \
    (id integer PRIMARY KEY, datetime text, sender_id integer, receiver_id integer, ask_message text, answer_message text, personal_id integer)")

# id : 0, datetime : 1, sender_id : 2, receiver_id : 3, ask_message : 4, answer_message : 5, personal_id : 6

conn.commit()


@client.event
async def on_ready():
    print("Bot is ready")


@client.command(aliases= ["핑", "반응속도"])
async def ping(ctx):
    await ctx.send("> Pong! {0} ms".format(round(client.latency * 100)))


@client.command(name= "eval")
@commands.is_owner()
async def _eval(ctx, *, command):
    respond = eval(command)

    if inspect.isawaitable(respond):
        await ctx.send("> " + str(await respond))
    else:
        await ctx.send("> " + str(respond))


@client.command(name= "회원가입")
async def register(ctx):
    cur.execute("SELECT * FROM user_profile WHERE user_id= ?", (ctx.message.author.id,))
    if len(cur.fetchall()) != 0:
        await ctx.send("> 이미 가입된 계정이 있습니다.")
        return None

    embed = discord.Embed(title= "서비스 이용약관 안내", description= "약관없음", colour= discord.Colour.red())

    msg = await ctx.send(embed= embed)
    await msg.add_reaction('⭕')
    await msg.add_reaction('❌')

    def check(reaction, user):
        return user == ctx.message.author and ( str(reaction.emoji) == '⭕' or str(reaction.emoji) == '❌' )

    try:
        reaction, user = await client.wait_for('reaction_add', timeout=30.0, check= check)
    except asyncio.TimeoutError:
        await ctx.send("> 시간이 초과하였습니다. 다시 시도해주세요")
    else:
        if str(reaction.emoji) == '❌':
            await ctx.send("> 이용약관에 동의하지 않았습니다.")
            return None
        else:
            await ctx.send("> 이용약관에 동의하셨습니다.")
    
    await ctx.send("> 프로필 검색에 이용할 아이디를 작성해주세요. ( 5자 이상 15자 이하 )")

    p = re.compile('[ㄱ-ㅎ가-하]+')

    while True:
        try:
            msg = await client.wait_for('message', timeout=30.0, check= lambda m: 5 <= len(m.content) <= 15 and m.author.id == ctx.message.author.id)
        except asyncio.TimeoutError:
            await ctx.send("> 시간이 초과하였습니다. 다시 시도해주세요")
            break
        else:
            cur.execute("SELECT * FROM user_profile WHERE custom_id= ?", (msg.content,))
            if len(cur.fetchall()) != 0 or p.match(msg.content) != None:
                await ctx.send("> 해당 아이디를 사용할 수 없습니다. 다시 작성해주세요.")
                continue

            cur.execute("INSERT INTO user_profile (user_id, custom_id, nickname) VALUES (?, ?, ?)", (ctx.message.author.id, msg.content, ctx.message.author.name))
            conn.commit()

            await ctx.send("> 회원가입에 성공하였습니다.")
            break


@client.command(aliases= ["프로필"])
async def view_profile(ctx, custom_id= None):
    cur.execute("SELECT * FROM user_profile WHERE user_id= ?", (ctx.message.author.id,))
    if len(cur.fetchall()) == 0:
        await ctx.send("> 아직 회원가입 하지 않았습니다! 회원가입을 우선 해주세요.")
        return None

    profile = None
    questions = None

    if custom_id == None:
        cur.execute("SELECT * FROM user_profile WHERE user_id= ?", (ctx.message.author.id,))
        profile = cur.fetchone()
    else:
        cur.execute("SELECT * FROM user_profile WHERE custom_id= ?", (custom_id,))
        profile = cur.fetchone()

    cur.execute("SELECT * FROM ask_messages WHERE receiver_id= ? ORDER BY personal_id asc", (int(profile[1]),))
    questions = cur.fetchall()

    embedpage = []
    max_page = math.ceil(len(questions) / 10)
    past_question = 0
    now_question = 10

    for i in range(max_page):
        embed = discord.Embed(title= "{0} 님의 프로필".format(profile[3]), description= "닉네임 :: {0}, ID :: {1}".format(profile[3], profile[2]), colour = discord.Colour.blue())

        try:
            for i in questions[past_question:now_question]:
                embed.add_field(name= "Q {0}. {1}".format(i[6], i[4]), value= "```{0}```".format(i[5]))
        except IndexError:
            continue
        
        embedpage.append(embed)

        past_question += 10
        now_question += 10

    if max_page == 0:
        embed = discord.Embed(title= "{0} 님의 프로필".format(profile[3]), description= "닉네임 :: {0}, ID :: {1}".format(profile[3], profile[2]), colour = discord.Colour.blue())
        embedpage.append(embed)

    msg = await ctx.send(embed= embedpage[0])
    await msg.add_reaction("⬅")
    await msg.add_reaction('➡')

    def check(reaction, user):
        return user == ctx.message.author and str(reaction.emoji) in ["⬅", '➡']

    pages = len(questions)
    now = 0

    while True:
        try:
            reaction, user = await client.wait_for('reaction_add', timeout = 30.0, check= check)

            if str(reaction) == "⬅":
                if now == 0:
                    await ctx.send("> 첫 페이지입니다.")
                else:
                    now -= 1
                    await msg.edit(embed= embedpage[now])
                await msg.remove_reaction("⬅", user)
            else:
                if now >= max_page - 1:
                    await ctx.send("> 마지막 페이지입니다.")
                else:
                    now += 1
                    await msg.edit(embed= embedpage[now])
                await msg.remove_reaction('➡', user)
        except asyncio.TimeoutError:
            await msg.clear_reaction("⬅")
            await msg.clear_reaction('➡')
            return None


@client.command(aliases= ["질문"])
async def question(ctx, custom_id= None, *, text):
    cur.execute("SELECT * FROM user_profile WHERE user_id= ?", (ctx.message.author.id,))
    if len(cur.fetchall()) == 0:
        await ctx.send("> 아직 회원가입 하지 않았습니다! 회원가입을 우선 해주세요.")
        return None

    if custom_id == None:
        await ctx.send("> 질문 대상자의 아이디를 작성해주세요")
        return None
    
    cur.execute("SELECT * FROM user_profile WHERE custom_id= ?", (custom_id,))
    if len(cur.fetchall()) == 0:
        await ctx.send("> 질문 대상자를 찾을 수 없습니다.")
        return None 
    
    if text == None:
        await ctx.send("> 질문 내용을 작성해주세요")
        return None
    
    cur.execute("SELECT * FROM user_profile WHERE custom_id= ?", (custom_id,))
    profile = cur.fetchone()
    receiver_id = profile[1]

    cur.execute("SELECT * FROM ask_messages WHERE receiver_id = ?", (receiver_id,))
    qnum = cur.fetchall()
    
    cur.execute("INSERT INTO ask_messages (datetime, sender_id, receiver_id, ask_message, answer_message, personal_id) VALUES (?, ?, ?, ?, ?, ?)", \
        (datetime.datetime.now(), ctx.message.author.id, receiver_id, text, "답변이 등록되지 않았습니다.", len(qnum) + 1))
    
    conn.commit()
    
    await ctx.send("> 질문이 등록되었습니다.")

    await client.get_user(int(profile[1])).send("> 새 질문이 왔습니다! 프로필을 확인해주세요!")


@client.command(aliases= ["답변"])
async def answer(ctx, question_id= None, *, text):
    cur.execute("SELECT * FROM user_profile WHERE user_id= ?", (ctx.message.author.id,))
    if len(cur.fetchall()) == 0:
        await ctx.send("> 아직 회원가입 하지 않았습니다! 회원가입을 우선 해주세요.")
        return None

    if question_id == None:
        await ctx.send("> 질문 ID를 작성해주세요")
        return None

    cur.execute("SELECT * FROM ask_messages WHERE id= ?", (question_id,))
    if len(cur.fetchall()) == 0:
        await ctx.send("> 질문을 찾을 수 없습니다.")
        return None
    
    if text == None:
        await ctx.send("> 답변 내용을 작성해주세요")
        return None
    
    cur.execute("UPDATE ask_messages SET answer_message= ? WHERE receiver_id= ? AND personal_id= ?", (text, ctx.message.author.id, int(question_id)))
    conn.commit()

    await ctx.send("> 답변이 등록되었습니다.")

    cur.execute("SELECT * FROM ask_messages WHERE receiver_id= ? AND personal_id= ?", (ctx.message.author.id, int(question_id)))
    _temp = cur.fetchone()
    sender_id = _temp[2]
    receiver_id = _temp[3]

    cur.execute("SELECT * FROM user_profile WHERE user_id= ?", (receiver_id,))
    receiver_customid = cur.fetchone()[2]

    await client.get_user(sender_id).send("> {0} ( {1} ) 님으로부터 답장이 왔습니다!".format(ctx.author, receiver_customid))


@client.command(aliases= ["질문삭제"])
async def remove_question(ctx, question_id = None):
    cur.execute("SELECT * FROM user_profile WHERE user_id= ?", (ctx.message.author.id,))
    if len(cur.fetchall()) == 0:
        await ctx.send("> 아직 회원가입 하지 않았습니다! 회원가입을 우선 해주세요.")
        return None

    if question_id == None:
        await ctx.send("> 질문 아이디를 작성해주세요")
        return None

    cur.execute("SELECT * FROM ask_messages WHERE receiver_id= ? AND personal_id= ?", (ctx.message.author.id, int(question_id)))
    if len(cur.fetchall()) == 0:
        await ctx.send("> 질문을 찾을 수 없습니다.")
        return None
    
    cur.execute("SELECT * FROM ask_messages WHERE receiver_id= ? AND personal_id= ?", (ctx.message.author.id, int(question_id)))
    question = cur.fetchone()

    if ctx.message.author.id != question[2]:
        await ctx.send("> 자신이 보낸 질문만 삭제할 수 있습니다.")
    else:
        cur.execute("DELETE FROM ask_messages WHERE receiver_id= ? AND personal_id= ?", (ctx.message.author.id, int(question_id)))
        conn.commit()
        await ctx.send("> 질문 삭제가 완료되었습니다.")


client.run(TOKEN)